"""Research Review Queue — human triage after Candidate VERIFIED.

Does not connect to Daily / Insight / Publishing.
Does not auto-set ClaimStatus.VERIFIED.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from discovery.models import CandidateRecord
from utils.helpers import now_iso

DEFAULT_QUEUE_PATH = Path("data/state/research_review_queue.json")


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


def make_queue_item_id(candidate_id: str) -> str:
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
    return f"rq-{digest}"


@dataclass
class ReviewQueueItem:
    queue_item_id: str
    candidate_id: str
    source_document_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    title: str = ""
    url: str = ""
    publisher: str = ""
    source_type: str = ""
    source_tier: str = ""
    published_at: str | None = None
    freshness_score: float = 0.0
    discovery_score: float = 0.0
    query: str = ""
    provider: str = ""
    created_at: str = ""
    review_status: ReviewStatus = ReviewStatus.PENDING
    review_reason: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "queue_item_id": self.queue_item_id,
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "title": self.title,
            "url": self.url,
            "publisher": self.publisher,
            "source_type": self.source_type,
            "source_tier": self.source_tier,
            "published_at": self.published_at,
            "freshness_score": self.freshness_score,
            "discovery_score": self.discovery_score,
            "query": self.query,
            "provider": self.provider,
            "created_at": self.created_at,
            "review_status": self.review_status.value,
            "review_reason": self.review_reason,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ReviewQueueItem:
        status_raw = data.get("review_status") or ReviewStatus.PENDING.value
        return cls(
            queue_item_id=str(data.get("queue_item_id") or ""),
            candidate_id=str(data.get("candidate_id") or ""),
            source_document_id=data.get("source_document_id"),
            evidence_ids=list(data.get("evidence_ids") or []),
            claim_ids=list(data.get("claim_ids") or []),
            title=str(data.get("title") or ""),
            url=str(data.get("url") or ""),
            publisher=str(data.get("publisher") or ""),
            source_type=str(data.get("source_type") or ""),
            source_tier=str(data.get("source_tier") or ""),
            published_at=data.get("published_at"),
            freshness_score=float(data.get("freshness_score") or 0.0),
            discovery_score=float(data.get("discovery_score") or 0.0),
            query=str(data.get("query") or ""),
            provider=str(data.get("provider") or ""),
            created_at=str(data.get("created_at") or ""),
            review_status=ReviewStatus(status_raw),
            review_reason=str(data.get("review_reason") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )

    @classmethod
    def from_candidate(cls, record: CandidateRecord) -> ReviewQueueItem:
        now = now_iso()
        return cls(
            queue_item_id=make_queue_item_id(record.candidate_id),
            candidate_id=record.candidate_id,
            source_document_id=record.source_document_id,
            evidence_ids=list(record.evidence_ids),
            claim_ids=list(record.claim_ids),
            title=record.candidate.title,
            url=record.canonical_url or record.candidate.url,
            publisher=record.publisher,
            source_type=record.source_type,
            source_tier=record.source_tier,
            published_at=record.published_at,
            freshness_score=record.freshness_score,
            discovery_score=record.discovery_score,
            query=record.candidate.query,
            provider=record.candidate.provider,
            created_at=now,
            review_status=ReviewStatus.PENDING,
            review_reason="",
            updated_at=now,
        )


class ResearchReviewQueue:
    """Durable JSON review queue keyed by queue_item_id / candidate_id."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_QUEUE_PATH
        self._by_id: dict[str, ReviewQueueItem] = {}
        self._by_candidate: dict[str, str] = {}

    def get(self, queue_item_id: str) -> ReviewQueueItem | None:
        return self._by_id.get(queue_item_id)

    def get_by_candidate(self, candidate_id: str) -> ReviewQueueItem | None:
        qid = self._by_candidate.get(candidate_id)
        return self._by_id.get(qid) if qid else None

    def all(self) -> list[ReviewQueueItem]:
        return list(self._by_id.values())

    def list_pending(self) -> list[ReviewQueueItem]:
        items = [i for i in self.all() if i.review_status is ReviewStatus.PENDING]
        items.sort(key=lambda i: (-i.discovery_score, i.created_at))
        return items

    def enqueue_verified(self, record: CandidateRecord) -> ReviewQueueItem | None:
        """Enqueue only VERIFIED candidates; same candidate → one queue item."""
        from discovery.models import CandidateStatus

        if record.status is not CandidateStatus.VERIFIED:
            return None
        existing = self.get_by_candidate(record.candidate_id)
        if existing is not None:
            # Refresh ranking metadata but keep review decision.
            existing.title = record.candidate.title or existing.title
            existing.publisher = record.publisher or existing.publisher
            existing.source_type = record.source_type or existing.source_type
            existing.source_tier = record.source_tier or existing.source_tier
            existing.published_at = record.published_at
            existing.freshness_score = record.freshness_score
            existing.discovery_score = record.discovery_score
            existing.query = record.candidate.query or existing.query
            existing.source_document_id = record.source_document_id or existing.source_document_id
            existing.evidence_ids = list(record.evidence_ids) or existing.evidence_ids
            existing.claim_ids = list(record.claim_ids) or existing.claim_ids
            existing.updated_at = now_iso()
            self._by_id[existing.queue_item_id] = existing
            return existing

        item = ReviewQueueItem.from_candidate(record)
        self._by_id[item.queue_item_id] = item
        self._by_candidate[record.candidate_id] = item.queue_item_id
        return item

    def set_status(
        self,
        queue_item_id: str,
        status: ReviewStatus,
        *,
        reason: str = "",
    ) -> ReviewQueueItem | None:
        item = self.get(queue_item_id) or self.get_by_candidate(queue_item_id)
        if item is None:
            return None
        item.review_status = status
        if reason:
            item.review_reason = reason
        item.updated_at = now_iso()
        self._by_id[item.queue_item_id] = item
        return item

    def load(self, path: str | Path | None = None) -> int:
        target = Path(path) if path else self.path
        self.path = target
        if not target.exists():
            return 0
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        rows = payload.get("items") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return 0
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = ReviewQueueItem.from_dict(row)
            if not item.queue_item_id or not item.candidate_id:
                continue
            self._by_id[item.queue_item_id] = item
            self._by_candidate[item.candidate_id] = item.queue_item_id
            count += 1
        return count

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": now_iso(),
            "items": [item.to_dict() for item in self.all()],
        }
        fd, tmp_name = tempfile.mkstemp(
            prefix="research_review_queue_", suffix=".json", dir=str(target.parent)
        )
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
    def load_or_create(cls, path: str | Path | None = None) -> ResearchReviewQueue:
        queue = cls(path=path)
        queue.load()
        return queue
