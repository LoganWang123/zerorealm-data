"""Discovery orchestration: search → pool → fetch → research verify."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from crawlers.base import RawItem
from discovery.dedupe import dedupe_candidates, normalize_url
from discovery.fetch import FetchResult, fetch_with_fallback
from discovery.models import CandidateRecord, CandidateStatus, SearchCandidate, make_candidate_id
from discovery.pool import DEFAULT_POOL_PATH, CandidatePool
from discovery.providers.base import SearchProvider
from discovery.scoring import score_candidate
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
    source_id_prefix: str = "discovery"
    results_per_query: int = 5


@dataclass
class DiscoveryRunSummary:
    queries: list[str] = field(default_factory=list)
    search_results: int = 0
    deduped: int = 0
    records: list[CandidateRecord] = field(default_factory=list)


class DiscoveryPipeline:
    """Independent discovery orchestrator (does not touch main.py crawl)."""

    def __init__(
        self,
        *,
        provider: SearchProvider,
        pool: CandidatePool | None = None,
        fetcher: Fetcher | None = None,
        config: DiscoveryPipelineConfig | None = None,
    ) -> None:
        self.config = config or DiscoveryPipelineConfig()
        self.provider = provider
        self.pool = pool or CandidatePool.load_or_create(self.config.pool_path)
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
        summary = DiscoveryRunSummary(
            queries=list(queries),
            search_results=len(all_hits),
            deduped=len(unique),
        )
        records: list[CandidateRecord] = []

        for cand in unique:
            canonical = normalize_url(cand.url) or cand.url
            candidate_id = make_candidate_id(cand.provider, canonical)
            now = now_iso()
            existing = self.pool.get_by_url(canonical) or self.pool.get(candidate_id)

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
                    # Already processed — do not create a second candidate / evidence chain.
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
                record.discovery_score = max(record.discovery_score, score_candidate(cand))
                record.last_seen_at = now
            else:
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
                    discovery_score=score_candidate(cand),
                    first_seen_at=now,
                    last_seen_at=now,
                )

            self.pool.upsert(record)

            if not self.config.fetch:
                records.append(record)
                continue

            try:
                fetch_result = self._fetch(cand.url or canonical)
            except Exception:
                record.status = CandidateStatus.FETCH_FAILED
                record.reason_codes = ["FETCH_FAILED"]
                self.pool.upsert(record)
                records.append(record)
                continue

            if not fetch_result.ok or fetch_result.item is None:
                record.status = CandidateStatus.FETCH_FAILED
                codes = list(fetch_result.reason_codes) or ["FETCH_FAILED"]
                if "FETCH_FAILED" not in codes:
                    codes.append("FETCH_FAILED")
                record.reason_codes = codes
                self.pool.upsert(record)
                records.append(record)
                continue

            raw = fetch_result.item
            record.status = CandidateStatus.FETCHED
            record.fetch_method = fetch_result.method
            record.raw_item_id = raw.id
            record.reason_codes = [c for c in fetch_result.reason_codes if c.startswith("HTML_")]
            record.metadata["raw_item"] = {
                "id": raw.id,
                "url": raw.url,
                "title": raw.title,
                "http_status": raw.http_status,
                "fetch_method": fetch_result.method,
            }
            body = (raw.content_text or "").strip()
            if not body:
                record.status = CandidateStatus.REJECTED
                record.reason_codes = list(dict.fromkeys([*record.reason_codes, "SOURCE_CONTENT_EMPTY"]))
                self.pool.upsert(record)
                records.append(record)
                continue

            if not self.config.verify:
                self.pool.upsert(record)
                records.append(record)
                continue

            self._verify(record, raw)
            self.pool.upsert(record)
            records.append(record)

        summary.records = records
        if self.config.persist:
            self.pool.save(self.config.pool_path)
        return summary

    def _fetch(self, url: str) -> FetchResult:
        source_id = f"{self.config.source_id_prefix}:{getattr(self.provider, 'name', 'search')}"
        if self.fetcher is None:
            return fetch_with_fallback(url, source_id=source_id)

        result = self.fetcher(url)
        if isinstance(result, FetchResult):
            return result
        # Legacy RawItem-returning mocks
        body = (result.content_text or "").strip()
        if not body:
            return FetchResult(
                item=None,
                method="html",
                reason_codes=["HTML_EMPTY", "FETCH_FAILED"],
                ok=False,
            )
        return FetchResult(item=result, method="html", reason_codes=[], ok=True)

    def _verify(self, record: CandidateRecord, raw: RawItem) -> None:
        from urllib.parse import urlsplit

        host = urlsplit(raw.url).netloc or "unknown"
        item = {
            "title": raw.title or record.candidate.title,
            "url": raw.url or record.canonical_url,
            "source_name": str(raw.metadata.get("source_name") or host),
            "published_at": raw.published_at or None,
            # excerpt comes from fetched body only — never snippet/provider_content
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
        record.source_document_id = atoms.source.id
        record.evidence_ids = [e.id for e in atoms.evidence]
        record.claim_ids = [c.id for c in atoms.claims]
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
        record.metadata["claims_status"] = [c.status.value for c in atoms.claims]

        issues = validate_discovery_atoms(atoms.claims, {atoms.source.id: atoms.source})
        blocking = [i for i in issues if i.severity == "error"]
        if has_blocking_issues(issues):
            record.status = CandidateStatus.REJECTED
            record.reason_codes = sorted({i.code for i in blocking}) or ["CLAIM_UNSUPPORTED"]
            record.verified_at = now_iso()
            return

        record.status = CandidateStatus.VERIFIED
        record.reason_codes = [c for c in record.reason_codes if c.startswith("HTML_")]
        record.verified_at = now_iso()
