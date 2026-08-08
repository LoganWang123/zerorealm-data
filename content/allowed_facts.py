"""Allowed Facts context for controlled generation — VERIFIED claims only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from content.brief import build_editorial_brief
from content.models import ContentCandidate, StatementKind
from research.atom_store import ResearchAtomStore
from research.models import ClaimStatus


@dataclass
class AllowedClaim:
    claim_id: str
    text: str
    evidence_ids: list[str] = field(default_factory=list)
    source_document_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AllowedNumericClaim:
    claim_id: str
    text: str
    numeric_kind: str
    formula: str = ""
    inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AllowedSource:
    source_document_id: str
    url: str = ""
    title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AllowedFactsContext:
    """Generator-safe fact context. Never includes snippets or draft claims."""

    content_candidate_id: str
    content_type: str
    working_title: str
    primary_signal: str
    research_question: str
    allowed_claims: list[AllowedClaim] = field(default_factory=list)
    allowed_numeric_claims: list[AllowedNumericClaim] = field(default_factory=list)
    allowed_sources: list[AllowedSource] = field(default_factory=list)
    fact_inference_boundaries: dict = field(default_factory=dict)
    evidence_gaps: list[str] = field(default_factory=list)
    prohibited_claims: list[str] = field(default_factory=list)
    experiment_parameters: list[dict] = field(default_factory=list)
    content_requirements: dict = field(default_factory=dict)
    allowed_entities: list[str] = field(default_factory=list)
    allowed_numbers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "content_candidate_id": self.content_candidate_id,
            "content_type": self.content_type,
            "working_title": self.working_title,
            "primary_signal": self.primary_signal,
            "research_question": self.research_question,
            "allowed_claims": [c.to_dict() for c in self.allowed_claims],
            "allowed_numeric_claims": [c.to_dict() for c in self.allowed_numeric_claims],
            "allowed_sources": [s.to_dict() for s in self.allowed_sources],
            "fact_inference_boundaries": dict(self.fact_inference_boundaries),
            "evidence_gaps": list(self.evidence_gaps),
            "prohibited_claims": list(self.prohibited_claims),
            "experiment_parameters": list(self.experiment_parameters),
            "content_requirements": dict(self.content_requirements),
            "allowed_entities": list(self.allowed_entities),
            "allowed_numbers": list(self.allowed_numbers),
        }


def _extract_numbers(text: str) -> list[str]:
    import re

    pattern = re.compile(
        r"\d+(?:\.\d+)?\s*(?:%|亿元|万元|元/柜|元|SKU|台|天|小时|百分点|倍)|"
        r"第\s*\d+\s*天|"
        r"预测\s*\d+%?|"
        r"Prediction\s*\d+%?",
        re.I,
    )
    return [m.group(0).strip() for m in pattern.finditer(text or "")]


def build_allowed_facts(
    candidate: ContentCandidate,
    *,
    atom_store: ResearchAtomStore | None = None,
) -> AllowedFactsContext:
    """Build generator context strictly from VERIFIED claims on the candidate."""
    if not candidate.brief:
        build_editorial_brief(candidate)

    brief = candidate.brief or {}
    allowed_claims: list[AllowedClaim] = []
    allowed_numeric: list[AllowedNumericClaim] = []
    allowed_entities: set[str] = set(candidate.companies or [])
    allowed_numbers: set[str] = set()

    for stmt in candidate.statements:
        if stmt.kind is not StatementKind.FACT:
            continue
        for cid in stmt.claim_ids:
            if atom_store is not None:
                claim = atom_store.get_claim(cid)
                if claim is None or claim.status is not ClaimStatus.VERIFIED:
                    continue
                text = claim.text
                evidence_ids = list(claim.evidence_ids)
                source_ids = list(claim.source_ids)
            else:
                text = stmt.text
                evidence_ids = list(candidate.evidence_ids)
                source_ids = list(candidate.source_document_ids)
            allowed_claims.append(
                AllowedClaim(
                    claim_id=cid,
                    text=text,
                    evidence_ids=evidence_ids,
                    source_document_ids=source_ids,
                )
            )
            for num in _extract_numbers(text):
                allowed_numbers.add(num)
            if stmt.numeric_kind:
                allowed_numeric.append(
                    AllowedNumericClaim(
                        claim_id=cid,
                        text=text,
                        numeric_kind=stmt.numeric_kind,
                        formula=stmt.formula,
                        inputs=list(stmt.inputs),
                    )
                )

    # Also accept claim_ids on candidate that are VERIFIED even without statement rows.
    if atom_store is not None:
        known = {c.claim_id for c in allowed_claims}
        for cid in candidate.claim_ids:
            if cid in known:
                continue
            claim = atom_store.get_claim(cid)
            if claim is None or claim.status is not ClaimStatus.VERIFIED:
                continue
            allowed_claims.append(
                AllowedClaim(
                    claim_id=cid,
                    text=claim.text,
                    evidence_ids=list(claim.evidence_ids),
                    source_document_ids=list(claim.source_ids),
                )
            )
            for num in _extract_numbers(claim.text):
                allowed_numbers.add(num)

    sources: list[AllowedSource] = []
    for sid in candidate.source_document_ids:
        url = ""
        title = ""
        if atom_store is not None and sid in atom_store.sources:
            src = atom_store.sources[sid]
            url = src.url or ""
            title = src.title or ""
        sources.append(AllowedSource(source_document_id=sid, url=url, title=title))

    experiments = [
        {
            **s.to_dict(),
            "zerorealm_suggested": True,
            "industry_standard": False,
        }
        for s in candidate.statements
        if s.kind is StatementKind.EXPERIMENT_PARAMETER
    ]
    for exp in experiments:
        for num in _extract_numbers(exp.get("text") or ""):
            allowed_numbers.add(num)

    for company in candidate.companies:
        if company:
            allowed_entities.add(company)

    # Common entities mentioned in allowed claim text — keep conservative allowlist.
    for claim in allowed_claims:
        for token in ("友宝", "东鹏", "东鹏饮料", "云拿", "映翰通", "ZeroRealm"):
            if token in claim.text:
                allowed_entities.add(token)

    return AllowedFactsContext(
        content_candidate_id=candidate.content_candidate_id,
        content_type=candidate.content_type.value,
        working_title=str(brief.get("working_title") or candidate.primary_signal),
        primary_signal=candidate.primary_signal,
        research_question=candidate.research_question,
        allowed_claims=allowed_claims,
        allowed_numeric_claims=allowed_numeric,
        allowed_sources=sources,
        fact_inference_boundaries=dict(brief.get("fact_inference_boundary") or {}),
        evidence_gaps=list(candidate.evidence_gaps),
        prohibited_claims=list(brief.get("prohibited_unsupported_claims") or candidate.evidence_gaps),
        experiment_parameters=experiments,
        content_requirements={
            "content_type": candidate.content_type.value,
            "primary_signal_count": candidate.primary_signal_count,
            "slug": candidate.slug,
            "no_new_companies": True,
            "no_new_numbers": True,
            "no_new_causal_links": True,
            "no_industry_standard_without_source": True,
            "no_prediction_without_methodology": True,
        },
        allowed_entities=sorted(allowed_entities),
        allowed_numbers=sorted(allowed_numbers),
    )
