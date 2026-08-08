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


def make_candidate_id(provider: str, canonical_url: str) -> str:
    """Stable id per provider + canonical URL (query-independent)."""
    raw = f"{provider}|{canonical_url}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"cand-{digest}"


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

    def candidate_id_for(self, canonical_url: str) -> str:
        return make_candidate_id(self.provider, canonical_url)


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
    first_seen_at: str = ""
    last_seen_at: str = ""
    fetch_method: str = ""
    # Source quality / freshness (ranking metadata — not evidence truth)
    source_type: str = ""
    source_tier: str = ""
    publisher: str = ""
    canonical_domain: str = ""
    is_official: bool = False
    published_at: str | None = None
    published_at_source: str = "unknown"
    published_at_confidence: str = "low"
    modified_at: str | None = None
    modified_at_source: str = "unknown"
    freshness_score: float = 0.0
    source_cluster_id: str = ""
    source_role: str = ""
    review_queue_id: str | None = None
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
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "original_url": self.candidate.url or self.canonical_url,
            "fetch_method": self.fetch_method,
        }

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "canonical_url": self.canonical_url,
            "provider": self.candidate.provider,
            "query": self.candidate.query,
            "title": self.candidate.title,
            "discovered_at": self.candidate.discovered_at,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "score": self.discovery_score,
            "discovery_score": self.discovery_score,
            "reason_codes": list(self.reason_codes),
            "verified_at": self.verified_at,
            "raw_item_id": self.raw_item_id,
            "source_document_id": self.source_document_id,
            "evidence_ids": list(self.evidence_ids),
            "claim_ids": list(self.claim_ids),
            "fetch_method": self.fetch_method,
            "source_type": self.source_type,
            "source_tier": self.source_tier,
            "publisher": self.publisher,
            "canonical_domain": self.canonical_domain,
            "is_official": self.is_official,
            "published_at": self.published_at,
            "published_at_source": self.published_at_source,
            "published_at_confidence": self.published_at_confidence,
            "modified_at": self.modified_at,
            "modified_at_source": self.modified_at_source,
            "freshness_score": self.freshness_score,
            "source_cluster_id": self.source_cluster_id,
            "source_role": self.source_role,
            "review_queue_id": self.review_queue_id,
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

    @classmethod
    def from_dict(cls, data: dict) -> CandidateRecord:
        cand_data = data.get("candidate") or {}
        candidate = SearchCandidate(
            provider=str(cand_data.get("provider") or data.get("provider") or "anysearch"),
            query=str(cand_data.get("query") or data.get("query") or ""),
            title=str(cand_data.get("title") or data.get("title") or ""),
            url=str(cand_data.get("url") or data.get("canonical_url") or ""),
            snippet=str(cand_data.get("snippet") or ""),
            provider_content=str(cand_data.get("provider_content") or ""),
            rank=int(cand_data.get("rank") or 0),
            discovered_at=str(cand_data.get("discovered_at") or data.get("discovered_at") or ""),
            language=str(cand_data.get("language") or "zh-CN"),
            evidence_eligible=False,
        )
        status_raw = data.get("status") or CandidateStatus.DISCOVERED.value
        return cls(
            candidate_id=str(data.get("candidate_id") or ""),
            status=CandidateStatus(status_raw),
            candidate=candidate,
            canonical_url=str(data.get("canonical_url") or ""),
            discovery_score=float(data.get("discovery_score") or data.get("score") or 0.0),
            reason_codes=list(data.get("reason_codes") or []),
            verified_at=data.get("verified_at"),
            raw_item_id=data.get("raw_item_id"),
            source_document_id=data.get("source_document_id"),
            evidence_ids=list(data.get("evidence_ids") or []),
            claim_ids=list(data.get("claim_ids") or []),
            first_seen_at=str(data.get("first_seen_at") or candidate.discovered_at or ""),
            last_seen_at=str(data.get("last_seen_at") or ""),
            fetch_method=str(data.get("fetch_method") or ""),
            source_type=str(data.get("source_type") or ""),
            source_tier=str(data.get("source_tier") or ""),
            publisher=str(data.get("publisher") or ""),
            canonical_domain=str(data.get("canonical_domain") or ""),
            is_official=bool(data.get("is_official") or False),
            published_at=data.get("published_at"),
            published_at_source=str(data.get("published_at_source") or "unknown"),
            published_at_confidence=str(data.get("published_at_confidence") or "low"),
            modified_at=data.get("modified_at"),
            modified_at_source=str(data.get("modified_at_source") or "unknown"),
            freshness_score=float(data.get("freshness_score") or 0.0),
            source_cluster_id=str(data.get("source_cluster_id") or ""),
            source_role=str(data.get("source_role") or ""),
            review_queue_id=data.get("review_queue_id"),
            metadata=dict(data.get("metadata") or {}),
        )
