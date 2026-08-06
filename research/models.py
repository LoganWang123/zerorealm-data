"""Core research domain models.

These models hold long-lived knowledge assets. Publishing still uses
``publishing.article.Article`` via adapters; do not replace Article here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class ClaimType(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    OPINION = "opinion"


class ClaimStatus(str, Enum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def _stable_id(*parts: str, prefix: str) -> str:
    raw = "|".join(part.strip() for part in parts if part is not None)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


@dataclass
class SourceDocument:
    """Original public source document."""

    id: str
    url: str
    title: str
    source_name: str
    published_at: str | None = None
    fetched_at: str = ""
    raw_excerpt: str = ""
    credibility: str = "medium"


@dataclass
class Evidence:
    """Evidence excerpt supporting a claim."""

    id: str
    source_id: str
    quote: str
    locator: str = ""


@dataclass
class Claim:
    """A fact, inference, or opinion with review state."""

    id: str
    text: str
    type: ClaimType
    status: ClaimStatus
    confidence: Confidence
    source_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    based_on_claim_ids: list[str] = field(default_factory=list)
    reviewed_at: str | None = None
    review_note: str = ""


@dataclass
class IndustrySignal:
    """Industry signal aligned with public ``signals.json`` items."""

    id: str
    slug: str
    title: str
    summary: str
    why_it_matters: str
    affected_roles: list[str]
    judgment: str
    claim_ids: list[str]
    source_ids: list[str]
    verification_status: str
    company_ids: list[str] = field(default_factory=list)
    published_at: str = ""
    tags: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict:
        """Compatibility wrapper; prefer ``research.serialization.serialize_signal``."""
        from research.serialization import serialize_signal

        return serialize_signal(self)


@dataclass
class CompanyProfile:
    """Smart-cabinet / chain company profile."""

    id: str
    slug: str
    name: str
    summary: str
    core_business: str = ""
    products: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    business_model: str = ""
    related_case_ids: list[str] = field(default_factory=list)
    related_signal_ids: list[str] = field(default_factory=list)
    verified_at: str = ""
    status: str = "draft"  # draft | approved | published


@dataclass
class CaseStudy:
    """Structured case study."""

    id: str
    slug: str
    title: str
    problem: str
    solution: str
    how_it_works: str
    public_results: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    company_ids: list[str] = field(default_factory=list)
    status: str = "draft"  # draft | approved | published


@dataclass
class MetricDefinition:
    """Operational metric dictionary entry."""

    id: str
    slug: str
    name: str
    definition: str
    formula: str = ""
    applicable_scenarios: list[str] = field(default_factory=list)
    common_pitfalls: list[str] = field(default_factory=list)
    related_case_ids: list[str] = field(default_factory=list)
    status: str = "draft"  # draft | approved | published


@dataclass
class Topic:
    """Editorial / research topic linking multiple assets."""

    id: str
    slug: str
    title: str
    summary: str = ""
    signal_ids: list[str] = field(default_factory=list)
    company_ids: list[str] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)
    metric_ids: list[str] = field(default_factory=list)
    status: str = "draft"  # draft | approved | published


@dataclass
class ResearchBrief:
    """Composable research package used before channel adaptation."""

    id: str
    slug: str
    title: str
    summary: str
    signal_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    company_ids: list[str] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)
    metric_ids: list[str] = field(default_factory=list)
    topic_ids: list[str] = field(default_factory=list)
    status: str = "draft"


@dataclass
class PublicationDraft:
    """Channel-neutral draft metadata (filled by later exporters)."""

    id: str
    brief_id: str
    channel: str
    title: str
    status: str = "draft"
    artifact_path: str = ""


def make_source_id(url: str, title: str = "") -> str:
    return _stable_id(url, title, prefix="src")


def make_claim_id(text: str, claim_type: ClaimType | str) -> str:
    kind = claim_type.value if isinstance(claim_type, ClaimType) else str(claim_type)
    return _stable_id(kind, text, prefix="cl")


def make_evidence_id(source_id: str, quote: str) -> str:
    return _stable_id(source_id, quote, prefix="ev")
