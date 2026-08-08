"""Content pipeline models — Candidate → Brief → Draft → Package (no publish)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum

from utils.helpers import now_iso


class ContentType(str, Enum):
    DAILY = "daily"
    INSIGHT = "insight"


class ContentCandidateStatus(str, Enum):
    DRAFT = "DRAFT"
    GATE_FAILED = "GATE_FAILED"
    READY_FOR_EDITORIAL = "READY_FOR_EDITORIAL"
    REJECTED = "REJECTED"


class EditorialStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_EDIT = "NEEDS_EDIT"


class StatementKind(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT_PARAMETER = "EXPERIMENT_PARAMETER"


class NumericKind(str, Enum):
    SOURCE_FACT = "SOURCE_FACT"
    DERIVED_METRIC = "DERIVED_METRIC"
    EXPERIMENT_PARAMETER = "EXPERIMENT_PARAMETER"


def make_content_candidate_id(content_type: str, primary_key: str) -> str:
    raw = f"{content_type}|{primary_key}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"cc-{digest}"


def make_content_id(content_type: str, slug: str) -> str:
    raw = f"{content_type}|{slug}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"ct-{digest}"


@dataclass
class ContentStatement:
    kind: StatementKind
    text: str
    claim_ids: list[str] = field(default_factory=list)
    numeric_kind: str | None = None
    formula: str = ""
    inputs: list[str] = field(default_factory=list)
    labeled_experiment: bool = False

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "claim_ids": list(self.claim_ids),
            "numeric_kind": self.numeric_kind,
            "formula": self.formula,
            "inputs": list(self.inputs),
            "labeled_experiment": self.labeled_experiment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContentStatement:
        return cls(
            kind=StatementKind(data.get("kind") or StatementKind.FACT.value),
            text=str(data.get("text") or ""),
            claim_ids=list(data.get("claim_ids") or []),
            numeric_kind=data.get("numeric_kind"),
            formula=str(data.get("formula") or ""),
            inputs=list(data.get("inputs") or []),
            labeled_experiment=bool(data.get("labeled_experiment") or False),
        )


@dataclass
class ContentCandidate:
    content_candidate_id: str
    content_type: ContentType
    topic: str = ""
    companies: list[str] = field(default_factory=list)
    primary_signal: str = ""
    research_question: str = ""
    knowledge_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    source_document_ids: list[str] = field(default_factory=list)
    independent_source_count: int = 0
    freshness_hours: float | None = None
    candidate_reason: str = ""
    evidence_gaps: list[str] = field(default_factory=list)
    primary_signal_count: int = 1
    theme_consistency: bool = True
    statements: list[ContentStatement] = field(default_factory=list)
    status: ContentCandidateStatus = ContentCandidateStatus.DRAFT
    editorial_status: EditorialStatus = EditorialStatus.PENDING
    gate_result: dict = field(default_factory=dict)
    brief: dict = field(default_factory=dict)
    draft: dict = field(default_factory=dict)
    package: dict = field(default_factory=dict)
    slug: str = ""
    content_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content_candidate_id": self.content_candidate_id,
            "content_type": self.content_type.value,
            "topic": self.topic,
            "companies": list(self.companies),
            "primary_signal": self.primary_signal,
            "research_question": self.research_question,
            "knowledge_ids": list(self.knowledge_ids),
            "claim_ids": list(self.claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "source_document_ids": list(self.source_document_ids),
            "independent_source_count": self.independent_source_count,
            "freshness_hours": self.freshness_hours,
            "candidate_reason": self.candidate_reason,
            "evidence_gaps": list(self.evidence_gaps),
            "primary_signal_count": self.primary_signal_count,
            "theme_consistency": self.theme_consistency,
            "statements": [s.to_dict() for s in self.statements],
            "status": self.status.value,
            "editorial_status": self.editorial_status.value,
            "gate_result": dict(self.gate_result),
            "brief": dict(self.brief),
            "draft": dict(self.draft),
            "package": dict(self.package),
            "slug": self.slug,
            "content_id": self.content_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContentCandidate:
        return cls(
            content_candidate_id=str(data.get("content_candidate_id") or ""),
            content_type=ContentType(data.get("content_type") or ContentType.DAILY.value),
            topic=str(data.get("topic") or ""),
            companies=list(data.get("companies") or []),
            primary_signal=str(data.get("primary_signal") or ""),
            research_question=str(data.get("research_question") or ""),
            knowledge_ids=list(data.get("knowledge_ids") or []),
            claim_ids=list(data.get("claim_ids") or []),
            evidence_ids=list(data.get("evidence_ids") or []),
            source_document_ids=list(data.get("source_document_ids") or []),
            independent_source_count=int(data.get("independent_source_count") or 0),
            freshness_hours=(
                float(data["freshness_hours"]) if data.get("freshness_hours") is not None else None
            ),
            candidate_reason=str(data.get("candidate_reason") or ""),
            evidence_gaps=list(data.get("evidence_gaps") or []),
            primary_signal_count=int(data.get("primary_signal_count") or 1),
            theme_consistency=bool(data.get("theme_consistency", True)),
            statements=[ContentStatement.from_dict(s) for s in (data.get("statements") or [])],
            status=ContentCandidateStatus(data.get("status") or ContentCandidateStatus.DRAFT.value),
            editorial_status=EditorialStatus(
                data.get("editorial_status") or EditorialStatus.PENDING.value
            ),
            gate_result=dict(data.get("gate_result") or {}),
            brief=dict(data.get("brief") or {}),
            draft=dict(data.get("draft") or {}),
            package=dict(data.get("package") or {}),
            slug=str(data.get("slug") or ""),
            content_id=str(data.get("content_id") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


def touch_timestamps(candidate: ContentCandidate) -> ContentCandidate:
    now = now_iso()
    if not candidate.created_at:
        candidate.created_at = now
    candidate.updated_at = now
    return candidate
