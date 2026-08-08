"""Discovery orchestration: search → pool → fetch → research verify."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from crawlers.base import RawItem
from discovery.dedupe import dedupe_candidates, normalize_url
from discovery.fetch import fetch_url_as_raw_item
from discovery.models import CandidateRecord, CandidateStatus, SearchCandidate
from discovery.pool import CandidatePool
from discovery.providers.base import SearchProvider
from discovery.scoring import score_candidate
from research.intake import news_to_research_atoms
from research.validators import has_blocking_issues, validate_discovery_atoms
from utils.helpers import now_iso

Fetcher = Callable[[str], RawItem]


@dataclass
class DiscoveryPipelineConfig:
    fetch: bool = True
    verify: bool = True
    persist: bool = False
    pool_path: str = "data/candidates/pool.json"
    source_id_prefix: str = "discovery"


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
        self.provider = provider
        self.pool = pool or CandidatePool()
        self.fetcher = fetcher or (
            lambda url: fetch_url_as_raw_item(
                url,
                source_id=f"{(config or DiscoveryPipelineConfig()).source_id_prefix}:{getattr(provider, 'name', 'search')}",
            )
        )
        self.config = config or DiscoveryPipelineConfig()

    def run(self, query: str, *, limit: int = 10) -> list[CandidateRecord]:
        hits = self.provider.search(query, limit=limit)
        unique = dedupe_candidates(hits)
        records: list[CandidateRecord] = []

        for cand in unique:
            canonical = normalize_url(cand.url) or cand.url
            existing = self.pool.get_by_url(canonical)
            if existing and existing.status in {
                CandidateStatus.VERIFIED,
                CandidateStatus.FETCHED,
                CandidateStatus.REJECTED,
                CandidateStatus.FETCH_FAILED,
            }:
                # Already processed this URL in this pool — do not re-fetch / re-evidence.
                records.append(existing)
                continue

            record = CandidateRecord(
                candidate_id=cand.candidate_id(),
                status=CandidateStatus.DISCOVERED,
                candidate=SearchCandidate(
                    provider=cand.provider,
                    query=cand.query or query,
                    title=cand.title,
                    url=cand.url,
                    snippet=cand.snippet,
                    provider_content=cand.provider_content,
                    rank=cand.rank,
                    discovered_at=cand.discovered_at or now_iso(),
                    language=cand.language,
                    evidence_eligible=False,
                ),
                canonical_url=canonical,
                discovery_score=score_candidate(cand),
            )
            self.pool.upsert(record)

            if not self.config.fetch:
                records.append(record)
                continue

            try:
                # Fetch the original host/path; canonical URL is only for dedupe keys.
                # (Stripping www. for dedupe must not break live fetches.)
                raw = self.fetcher(cand.url or canonical)
            except Exception:
                record.status = CandidateStatus.FETCH_FAILED
                record.reason_codes = ["SOURCE_FETCH_FAILED"]
                self.pool.upsert(record)
                records.append(record)
                continue

            record.status = CandidateStatus.FETCHED
            record.raw_item_id = raw.id
            record.metadata["raw_item"] = {
                "id": raw.id,
                "url": raw.url,
                "title": raw.title,
                "http_status": raw.http_status,
            }
            # Hard rule: never use search snippet / provider_content as body.
            body = (raw.content_text or "").strip()
            if not body:
                record.status = CandidateStatus.REJECTED
                record.reason_codes = ["SOURCE_CONTENT_EMPTY"]
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

        if self.config.persist:
            self.pool.save(self.config.pool_path)
        return records

    def _verify(self, record: CandidateRecord, raw: RawItem) -> None:
        host = urlsplit(raw.url).netloc or "unknown"
        item = {
            "title": raw.title or record.candidate.title,
            "url": raw.url or record.canonical_url,
            "source_name": str(raw.metadata.get("source_name") or host),
            "published_at": raw.published_at or None,
            # excerpt comes from fetched body only — never snippet/provider_content
            "excerpt": (raw.content_text or "").strip()[:2000],
        }
        if not item["url"]:
            record.status = CandidateStatus.REJECTED
            record.reason_codes = ["SOURCE_LINEAGE_INCOMPLETE"]
            return

        atoms = news_to_research_atoms(item)
        # Attach discovery metadata on RawItem side only; SourceDocument stays provenance-clean.
        record.source_document_id = atoms.source.id
        record.evidence_ids = [e.id for e in atoms.evidence]
        record.claim_ids = [c.id for c in atoms.claims]
        record.metadata["discovery"] = {
            "provider": record.candidate.provider,
            "query": record.candidate.query,
            "discovered_at": record.candidate.discovered_at,
            "candidate_id": record.candidate_id,
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
        record.reason_codes = []
        record.verified_at = now_iso()
