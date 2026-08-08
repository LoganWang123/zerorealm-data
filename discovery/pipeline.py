"""Discovery orchestration: search → pool → fetch → research verify → review queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit

from crawlers.base import RawItem
from discovery.clustering import assign_clusters, content_fingerprint
from discovery.dedupe import dedupe_candidates, normalize_url
from discovery.fetch import FetchResult, fetch_with_fallback
from discovery.freshness import freshness_score
from discovery.models import CandidateRecord, CandidateStatus, SearchCandidate, make_candidate_id
from discovery.pool import DEFAULT_POOL_PATH, CandidatePool
from discovery.providers.base import SearchProvider
from discovery.publication_date import extract_publication_dates
from discovery.review_queue import DEFAULT_QUEUE_PATH, ResearchReviewQueue
from discovery.scoring import score_candidate, score_candidate_breakdown
from discovery.source_quality import classify_source
from research.atom_store import DEFAULT_ATOMS_PATH, ResearchAtomStore
from research.intake import news_to_research_atoms
from research.validators import has_blocking_issues, validate_discovery_atoms
from utils.helpers import now_iso

Fetcher = Callable[[str], RawItem | FetchResult]


@dataclass
class DiscoveryPipelineConfig:
    fetch: bool = True
    verify: bool = True
    persist: bool = True
    pool_path: str = str(DEFAULT_POOL_PATH)
    queue_path: str = str(DEFAULT_QUEUE_PATH)
    atoms_path: str = str(DEFAULT_ATOMS_PATH)
    source_id_prefix: str = "discovery"
    results_per_query: int = 5
    max_candidates_per_run: int | None = None
    intent: str = "research"
    freshness_window: str | None = None
    topic_terms: list[str] = field(default_factory=list)
    company_terms: list[str] = field(default_factory=list)


@dataclass
class DiscoveryRunSummary:
    queries: list[str] = field(default_factory=list)
    search_results: int = 0
    deduped: int = 0
    records: list[CandidateRecord] = field(default_factory=list)
    queue_enqueued: int = 0


class DiscoveryPipeline:
    """Independent discovery orchestrator (does not touch main.py crawl)."""

    def __init__(
        self,
        *,
        provider: SearchProvider,
        pool: CandidatePool | None = None,
        review_queue: ResearchReviewQueue | None = None,
        atom_store: ResearchAtomStore | None = None,
        fetcher: Fetcher | None = None,
        config: DiscoveryPipelineConfig | None = None,
    ) -> None:
        self.config = config or DiscoveryPipelineConfig()
        self.provider = provider
        self.pool = pool or CandidatePool.load_or_create(self.config.pool_path)
        self.review_queue = review_queue or ResearchReviewQueue.load_or_create(
            self.config.queue_path
        )
        self.atom_store = atom_store or ResearchAtomStore.load_or_create(self.config.atoms_path)
        self.fetcher = fetcher

    def run(self, query: str, *, limit: int = 10) -> list[CandidateRecord]:
        summary = self.run_queries([query], results_per_query=limit)
        return summary.records

    def run_queries(
        self,
        queries: list[str],
        *,
        results_per_query: int | None = None,
    ) -> DiscoveryRunSummary:
        per_query = max(1, min(int(results_per_query or self.config.results_per_query), 10))
        all_hits: list[SearchCandidate] = []
        for query in queries:
            q = str(query).strip()
            if not q:
                continue
            all_hits.extend(self.provider.search(q, limit=per_query))

        unique = dedupe_candidates(all_hits)
        clusters = assign_clusters(unique)
        unique.sort(
            key=lambda c: score_candidate(
                c,
                intent=self.config.intent,
                freshness_window=self.config.freshness_window,
                topic_terms=self.config.topic_terms,
                company_terms=self.config.company_terms,
                syndication_penalty=(clusters.get(c.url).syndication_penalty if clusters.get(c.url) else 0.0),
            ),
            reverse=True,
        )
        if self.config.max_candidates_per_run:
            unique = unique[: max(1, int(self.config.max_candidates_per_run))]

        summary = DiscoveryRunSummary(
            queries=list(queries),
            search_results=len(all_hits),
            deduped=len(unique),
        )
        records: list[CandidateRecord] = []
        enqueued = 0

        for cand in unique:
            canonical = normalize_url(cand.url) or cand.url
            candidate_id = make_candidate_id(cand.provider, canonical)
            now = now_iso()
            existing = self.pool.get_by_url(canonical) or self.pool.get(candidate_id)
            cluster = clusters.get(cand.url)
            prelim = score_candidate_breakdown(
                cand,
                intent=self.config.intent,
                freshness_window=self.config.freshness_window,
                topic_terms=self.config.topic_terms,
                company_terms=self.config.company_terms,
                syndication_penalty=cluster.syndication_penalty if cluster else 0.0,
            )

            if existing is not None:
                existing = self.pool.touch(
                    canonical,
                    query=cand.query,
                    title=cand.title or existing.candidate.title,
                ) or existing
                if existing.status in {
                    CandidateStatus.VERIFIED,
                    CandidateStatus.FETCHED,
                    CandidateStatus.REJECTED,
                    CandidateStatus.FETCH_FAILED,
                }:
                    if existing.status is CandidateStatus.VERIFIED:
                        self._apply_quality_metadata(
                            existing,
                            published_at=existing.published_at,
                            html="",
                            syndication_penalty=cluster.syndication_penalty if cluster else 0.0,
                            cluster=cluster,
                        )
                        item = self.review_queue.enqueue_verified(existing)
                        if item is not None:
                            existing.review_queue_id = item.queue_item_id
                            enqueued += 1
                            self.pool.upsert(existing)
                    records.append(existing)
                    continue
                record = existing
                record.candidate = SearchCandidate(
                    provider=cand.provider,
                    query=cand.query,
                    title=cand.title or existing.candidate.title,
                    url=cand.url,
                    snippet=cand.snippet,
                    provider_content=cand.provider_content,
                    rank=cand.rank,
                    discovered_at=existing.candidate.discovered_at or cand.discovered_at or now,
                    language=cand.language,
                    evidence_eligible=False,
                )
                record.discovery_score = max(record.discovery_score, prelim.discovery_score)
                record.last_seen_at = now
            else:
                clf = classify_source(cand.url, title=cand.title)
                record = CandidateRecord(
                    candidate_id=candidate_id,
                    status=CandidateStatus.DISCOVERED,
                    candidate=SearchCandidate(
                        provider=cand.provider,
                        query=cand.query,
                        title=cand.title,
                        url=cand.url,
                        snippet=cand.snippet,
                        provider_content=cand.provider_content,
                        rank=cand.rank,
                        discovered_at=cand.discovered_at or now,
                        language=cand.language,
                        evidence_eligible=False,
                    ),
                    canonical_url=canonical,
                    discovery_score=prelim.discovery_score,
                    first_seen_at=now,
                    last_seen_at=now,
                    source_type=clf.source_type.value,
                    source_tier=clf.source_tier.value,
                    publisher=clf.publisher,
                    canonical_domain=clf.canonical_domain,
                    is_official=clf.is_official,
                    freshness_score=prelim.freshness,
                    source_cluster_id=cluster.source_cluster_id if cluster else "",
                    source_role=cluster.source_role.value if cluster else "",
                    metadata={"score_breakdown": prelim.to_dict()},
                )

            self.pool.upsert(record)

            if not self.config.fetch:
                records.append(record)
                continue

            try:
                fetch_result = self._fetch(cand.url or canonical)
            except Exception as exc:
                from discovery.fetch import classify_fetch_exception

                record.status = CandidateStatus.FETCH_FAILED
                record.reason_codes = list(
                    dict.fromkeys([*classify_fetch_exception(exc), "FETCH_FAILED"])
                )
                record.metadata["queue_skip_reason"] = "FETCH_FAILED"
                self.pool.upsert(record)
                records.append(record)
                continue

            if not fetch_result.ok or fetch_result.item is None:
                record.status = CandidateStatus.FETCH_FAILED
                codes = list(fetch_result.reason_codes) or ["FETCH_FAILED"]
                if "FETCH_FAILED" not in codes:
                    codes.append("FETCH_FAILED")
                record.reason_codes = codes
                record.metadata["queue_skip_reason"] = "FETCH_FAILED"
                record.metadata["fetch_diagnostics"] = fetch_result.diagnostics
                self.pool.upsert(record)
                records.append(record)
                continue

            raw = fetch_result.item
            record.status = CandidateStatus.FETCHED
            record.fetch_method = fetch_result.method
            record.raw_item_id = raw.id
            # Keep detailed fetch reasons that are useful (not only HTML_*).
            record.reason_codes = [
                c
                for c in fetch_result.reason_codes
                if c.startswith("HTML_") or c in {"JS_REQUIRED"}
            ]

            date_info = extract_publication_dates(
                html=raw.content_html or "",
                text=raw.content_text or "",
            )
            page_published = date_info.published_at
            record.published_at = page_published
            record.published_at_source = date_info.published_at_source
            record.published_at_confidence = date_info.published_at_confidence
            record.modified_at = date_info.modified_at
            record.modified_at_source = date_info.modified_at_source
            if date_info.date_conflict:
                record.reason_codes = list(
                    dict.fromkeys([*record.reason_codes, "PUBLICATION_DATE_CONFLICT"])
                )
            record.metadata["publication_date"] = date_info.to_dict()
            record.metadata["content_fingerprint"] = content_fingerprint(raw.content_text or "")
            record.metadata["raw_item"] = {
                "id": raw.id,
                "url": raw.url,
                "title": raw.title,
                "http_status": raw.http_status,
                "fetch_method": fetch_result.method,
                "published_at": page_published,
                "crawled_at": raw.crawled_at,
            }
            body = (raw.content_text or "").strip()
            if not body:
                record.status = CandidateStatus.REJECTED
                record.reason_codes = list(dict.fromkeys([*record.reason_codes, "SOURCE_CONTENT_EMPTY"]))
                record.metadata["queue_skip_reason"] = "SOURCE_CONTENT_EMPTY"
                self.pool.upsert(record)
                records.append(record)
                continue

            if not self.config.verify:
                self._apply_quality_metadata(
                    record,
                    published_at=page_published,
                    html=raw.content_html or "",
                    syndication_penalty=cluster.syndication_penalty if cluster else 0.0,
                    cluster=cluster,
                )
                self.pool.upsert(record)
                records.append(record)
                continue

            self._verify(record, raw, published_at=page_published)
            if record.status is CandidateStatus.VERIFIED:
                self._apply_quality_metadata(
                    record,
                    published_at=page_published,
                    html=raw.content_html or "",
                    syndication_penalty=cluster.syndication_penalty if cluster else 0.0,
                    cluster=cluster,
                )
                item = self.review_queue.enqueue_verified(record)
                if item is not None:
                    record.review_queue_id = item.queue_item_id
                    enqueued += 1
            else:
                record.metadata["queue_skip_reason"] = (
                    record.reason_codes[0] if record.reason_codes else record.status.value
                )
            self.pool.upsert(record)
            records.append(record)

        summary.records = records
        summary.queue_enqueued = enqueued
        if self.config.persist:
            self.pool.save(self.config.pool_path)
            self.review_queue.save(self.config.queue_path)
            self.atom_store.save(self.config.atoms_path)
        return summary

    def _apply_quality_metadata(
        self,
        record: CandidateRecord,
        *,
        published_at: str | None,
        html: str = "",
        syndication_penalty: float = 0.0,
        cluster=None,
    ) -> None:
        host = urlsplit(record.canonical_url or record.candidate.url).netloc or ""
        publisher_hint = str(
            (record.metadata.get("raw_item") or {}).get("source_name")
            or record.publisher
            or host
        )
        clf = classify_source(
            record.canonical_url or record.candidate.url,
            title=record.candidate.title,
            publisher=publisher_hint,
            html=html,
        )
        record.source_type = clf.source_type.value
        record.source_tier = clf.source_tier.value
        record.publisher = clf.publisher
        record.canonical_domain = clf.canonical_domain
        record.is_official = clf.is_official
        record.published_at = published_at
        record.freshness_score = freshness_score(
            published_at,
            intent=self.config.intent,
            freshness_window=self.config.freshness_window,
        )
        if cluster is not None:
            record.source_cluster_id = cluster.source_cluster_id
            record.source_role = cluster.source_role.value
        breakdown = score_candidate_breakdown(
            record.candidate,
            classification=clf,
            published_at=published_at,
            intent=self.config.intent,
            freshness_window=self.config.freshness_window,
            topic_terms=self.config.topic_terms,
            company_terms=self.config.company_terms,
            syndication_penalty=syndication_penalty,
        )
        record.discovery_score = breakdown.discovery_score
        record.metadata["score_breakdown"] = breakdown.to_dict()
        record.metadata["source_quality"] = clf.to_dict()

    def _fetch(self, url: str) -> FetchResult:
        source_id = f"{self.config.source_id_prefix}:{getattr(self.provider, 'name', 'search')}"
        if self.fetcher is None:
            return fetch_with_fallback(url, source_id=source_id)

        result = self.fetcher(url)
        if isinstance(result, FetchResult):
            return result
        body = (result.content_text or "").strip()
        if not body:
            return FetchResult(
                item=None,
                method="html",
                reason_codes=["HTML_EMPTY", "FETCH_FAILED"],
                ok=False,
            )
        return FetchResult(item=result, method="html", reason_codes=[], ok=True)

    def _verify(
        self,
        record: CandidateRecord,
        raw: RawItem,
        *,
        published_at: str | None,
    ) -> None:
        host = urlsplit(raw.url).netloc or "unknown"
        clf = classify_source(
            raw.url or record.canonical_url,
            title=raw.title or record.candidate.title,
            html=raw.content_html or "",
        )
        item = {
            "title": raw.title or record.candidate.title,
            "url": raw.url or record.canonical_url,
            "source_name": clf.publisher or str(raw.metadata.get("source_name") or host),
            "published_at": published_at,
            "excerpt": (raw.content_text or "").strip()[:2000],
            "discovery_provider": record.candidate.provider,
            "discovery_query": record.candidate.query,
            "discovery_candidate_id": record.candidate_id,
            "discovery_original_url": record.candidate.url or record.canonical_url,
        }
        if not item["url"]:
            record.status = CandidateStatus.REJECTED
            record.reason_codes = ["SOURCE_LINEAGE_INCOMPLETE"]
            return

        atoms = news_to_research_atoms(item)
        # Enrich source type from classification (not search snippet).
        atoms.source.source_type = clf.source_type.value
        record.source_document_id = atoms.source.id
        record.evidence_ids = [e.id for e in atoms.evidence]
        record.claim_ids = [c.id for c in atoms.claims]
        lineage = {
            "candidate_id": record.candidate_id,
            "discovery_provider": record.candidate.provider,
            "discovery_query": record.candidate.query,
            "intake": "discovery",
            "source_tier": clf.source_tier.value,
            "publisher": clf.publisher,
            "published_at": published_at,
            "published_at_source": record.published_at_source,
        }
        self.atom_store.upsert_atoms(
            source=atoms.source,
            evidence=atoms.evidence,
            claims=atoms.claims,
            lineage=lineage,
        )
        # Reflect protected statuses back onto candidate metadata.
        statuses = []
        for cid in record.claim_ids:
            stored = self.atom_store.get_claim(cid)
            statuses.append((stored.status.value if stored else "draft"))
        record.metadata["claims_status"] = statuses
        record.metadata["discovery"] = {
            "provider": record.candidate.provider,
            "query": record.candidate.query,
            "discovered_at": record.candidate.discovered_at,
            "candidate_id": record.candidate_id,
            "original_url": record.candidate.url or record.canonical_url,
        }
        record.metadata["source_discovery"] = {
            "discovery_provider": atoms.source.discovery_provider,
            "discovery_query": atoms.source.discovery_query,
            "discovery_candidate_id": atoms.source.discovery_candidate_id,
            "discovery_original_url": atoms.source.discovery_original_url,
        }

        issues = validate_discovery_atoms(atoms.claims, {atoms.source.id: atoms.source})
        blocking = [i for i in issues if i.severity == "error"]
        if has_blocking_issues(issues):
            record.status = CandidateStatus.REJECTED
            record.reason_codes = sorted({i.code for i in blocking}) or ["CLAIM_UNSUPPORTED"]
            record.verified_at = now_iso()
            return

        record.status = CandidateStatus.VERIFIED
        record.reason_codes = [
            c
            for c in record.reason_codes
            if c.startswith("HTML_") or c in {"JS_REQUIRED", "PUBLICATION_DATE_CONFLICT"}
        ]
        record.verified_at = now_iso()
