"""Durable Candidate Pool (Discovery state — not .cache, not Public Bundle)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from discovery.models import CandidateRecord, CandidateStatus
from utils.helpers import now_iso

DEFAULT_POOL_PATH = Path("data/state/candidate_pool.json")


class CandidatePool:
    """Durable candidate store keyed by candidate_id and canonical URL."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_POOL_PATH
        self._by_id: dict[str, CandidateRecord] = {}
        self._by_url: dict[str, str] = {}

    def upsert(self, record: CandidateRecord) -> CandidateRecord:
        existing = self._by_id.get(record.candidate_id) or self.get_by_url(record.canonical_url)
        now = now_iso()
        if existing is None:
            if not record.first_seen_at:
                record.first_seen_at = record.candidate.discovered_at or now
            if not record.last_seen_at:
                record.last_seen_at = now
        else:
            # Same canonical URL → update last_seen / query metadata, keep lineage ids.
            record.first_seen_at = existing.first_seen_at or record.first_seen_at or now
            record.last_seen_at = now
            if existing.status in {
                CandidateStatus.VERIFIED,
                CandidateStatus.FETCHED,
                CandidateStatus.REJECTED,
                CandidateStatus.FETCH_FAILED,
            }:
                # Preserve progressed state unless caller explicitly advanced further.
                if record.status == CandidateStatus.DISCOVERED:
                    record.status = existing.status
                    record.reason_codes = list(existing.reason_codes)
                    record.raw_item_id = existing.raw_item_id
                    record.source_document_id = existing.source_document_id
                    record.evidence_ids = list(existing.evidence_ids)
                    record.claim_ids = list(existing.claim_ids)
                    record.verified_at = existing.verified_at
                    record.fetch_method = existing.fetch_method or record.fetch_method
                    record.metadata = {**existing.metadata, **record.metadata}
            # Prefer newer query annotation but keep provider/url stable.
            if record.candidate.query:
                existing_query = existing.candidate.query
                record.metadata.setdefault("prior_queries", [])
                prior = record.metadata.get("prior_queries")
                if isinstance(prior, list) and existing_query and existing_query not in prior:
                    if existing_query != record.candidate.query:
                        prior.append(existing_query)

        self._by_id[record.candidate_id] = record
        key = (record.canonical_url or record.candidate.url or "").strip()
        if key:
            self._by_url[key] = record.candidate_id
        return record

    def touch(self, canonical_url: str, *, query: str = "", title: str = "") -> CandidateRecord | None:
        record = self.get_by_url(canonical_url)
        if record is None:
            return None
        record.last_seen_at = now_iso()
        if query:
            prior = record.metadata.setdefault("prior_queries", [])
            if isinstance(prior, list) and record.candidate.query and record.candidate.query not in prior:
                if record.candidate.query != query:
                    prior.append(record.candidate.query)
            record.candidate.query = query
        if title:
            record.candidate.title = title
        self._by_id[record.candidate_id] = record
        return record

    def get(self, candidate_id: str) -> CandidateRecord | None:
        return self._by_id.get(candidate_id)

    def get_by_url(self, canonical_url: str) -> CandidateRecord | None:
        cid = self._by_url.get(canonical_url)
        return self._by_id.get(cid) if cid else None

    def all(self) -> list[CandidateRecord]:
        return list(self._by_id.values())

    def update_status(
        self,
        candidate_id: str,
        status: CandidateStatus,
        *,
        reason_codes: list[str] | None = None,
    ) -> CandidateRecord | None:
        record = self._by_id.get(candidate_id)
        if record is None:
            return None
        record.status = status
        if reason_codes is not None:
            record.reason_codes = list(reason_codes)
        return record

    def load(self, path: str | Path | None = None) -> int:
        target = Path(path) if path else self.path
        self.path = target
        if not target.exists():
            return 0
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        rows = payload.get("candidates") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return 0
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            record = CandidateRecord.from_dict(row)
            if not record.candidate_id:
                continue
            self._by_id[record.candidate_id] = record
            key = (record.canonical_url or record.candidate.url or "").strip()
            if key:
                self._by_url[key] = record.candidate_id
            count += 1
        return count

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": now_iso(),
            "candidates": [record.to_dict() for record in self.all()],
        }
        fd, tmp_name = tempfile.mkstemp(prefix="candidate_pool_", suffix=".json", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @classmethod
    def load_or_create(cls, path: str | Path | None = None) -> CandidatePool:
        pool = cls(path=path)
        pool.load()
        return pool
