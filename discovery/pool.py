"""In-memory / optional on-disk candidate pool."""

from __future__ import annotations

import json
from pathlib import Path

from discovery.models import CandidateRecord, CandidateStatus


class CandidatePool:
    """Durable-ish candidate store keyed by candidate_id and canonical URL."""

    def __init__(self) -> None:
        self._by_id: dict[str, CandidateRecord] = {}
        self._by_url: dict[str, str] = {}

    def upsert(self, record: CandidateRecord) -> CandidateRecord:
        self._by_id[record.candidate_id] = record
        key = (record.canonical_url or record.candidate.url or "").strip()
        if key:
            self._by_url[key] = record.candidate_id
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

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.to_dict() for record in self.all()]
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
