"""Discovery domain models (candidates only — not Evidence)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class CandidateStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    FETCHED = "FETCHED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FETCH_FAILED = "FETCH_FAILED"


@dataclass
class SearchCandidate:
    """A search hit used only for discovery ranking/selection."""

    provider: str
    query: str
    title: str
    url: str
    snippet: str = ""
    provider_content: str = ""
    rank: int = 0
    discovered_at: str = ""
    language: str = "zh-CN"
    evidence_eligible: bool = False

    def candidate_id(self) -> str:
        raw = f"{self.provider}|{self.url}|{self.query}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"cand-{digest}"


@dataclass
class CandidateRecord:
    """Durable candidate pool entry with research lineage."""

    candidate_id: str
    status: CandidateStatus
    candidate: SearchCandidate
    canonical_url: str = ""
    discovery_score: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    verified_at: str | None = None
    raw_item_id: str | None = None
    source_document_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def lineage(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "raw_item_id": self.raw_item_id,
            "source_document_id": self.source_document_id,
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "discovery_provider": self.candidate.provider,
            "discovery_query": self.candidate.query,
            "discovered_at": self.candidate.discovered_at,
            "original_url": self.canonical_url or self.candidate.url,
        }

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "canonical_url": self.canonical_url,
            "discovery_score": self.discovery_score,
            "reason_codes": list(self.reason_codes),
            "verified_at": self.verified_at,
            "raw_item_id": self.raw_item_id,
            "source_document_id": self.source_document_id,
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "lineage": self.lineage,
            "candidate": {
                "provider": self.candidate.provider,
                "query": self.candidate.query,
                "title": self.candidate.title,
                "url": self.candidate.url,
                "snippet": self.candidate.snippet,
                "provider_content": self.candidate.provider_content,
                "rank": self.candidate.rank,
                "discovered_at": self.candidate.discovered_at,
                "language": self.candidate.language,
                "evidence_eligible": self.candidate.evidence_eligible,
            },
            "metadata": dict(self.metadata),
        }
