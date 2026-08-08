"""Controlled Content Generator — provider-abstracted, CI uses deterministic mock."""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from content.allowed_facts import AllowedFactsContext, build_allowed_facts
from content.models import ContentCandidate, ContentType
from research.atom_store import ResearchAtomStore
from utils.helpers import now_iso

GENERATOR_PROMPT_RULES = """
You must ONLY use Allowed Facts.
Do NOT invent: companies, dates, numbers, causal links, sources,
industry averages, industry standards, or prediction probabilities
unless they already exist in Allowed Facts.
FACT statements require claim_ids from allowed_claims.
INFERENCE requires supporting_claim_ids.
HYPOTHESIS must be explicitly unverified.
EXPERIMENT_PARAMETER must set zerorealm_suggested=true and industry_standard=false.
""".strip()


@dataclass
class DraftSection:
    title: str
    body: str
    claim_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "claim_ids": list(self.claim_ids),
        }

    @classmethod
    def from_dict(cls, data: dict) -> DraftSection:
        return cls(
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            claim_ids=list(data.get("claim_ids") or []),
        )


@dataclass
class DraftStatement:
    text: str
    statement_type: str  # FACT | INFERENCE | HYPOTHESIS | EXPERIMENT_PARAMETER
    claim_ids: list[str] = field(default_factory=list)
    supporting_claim_ids: list[str] = field(default_factory=list)
    numeric_kind: str | None = None
    formula: str = ""
    inputs: list[str] = field(default_factory=list)
    parameter_basis: str = ""
    zerorealm_suggested: bool = False
    industry_standard: bool = False
    pending_verification: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "statement_type": self.statement_type,
            "claim_ids": list(self.claim_ids),
            "supporting_claim_ids": list(self.supporting_claim_ids),
            "numeric_kind": self.numeric_kind,
            "formula": self.formula,
            "inputs": list(self.inputs),
            "parameter_basis": self.parameter_basis,
            "zerorealm_suggested": self.zerorealm_suggested,
            "industry_standard": self.industry_standard,
            "pending_verification": self.pending_verification,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DraftStatement:
        stype = str(
            data.get("statement_type") or data.get("kind") or "FACT"
        ).upper()
        return cls(
            text=str(data.get("text") or ""),
            statement_type=stype,
            claim_ids=list(data.get("claim_ids") or []),
            supporting_claim_ids=list(data.get("supporting_claim_ids") or data.get("claim_ids") or []),
            numeric_kind=data.get("numeric_kind"),
            formula=str(data.get("formula") or ""),
            inputs=list(data.get("inputs") or []),
            parameter_basis=str(data.get("parameter_basis") or ""),
            zerorealm_suggested=bool(data.get("zerorealm_suggested") or data.get("labeled_experiment") or False),
            industry_standard=bool(data.get("industry_standard") or False),
            pending_verification=bool(data.get("pending_verification") or False),
        )


def make_draft_id(content_id: str, revision: str = "1") -> str:
    digest = hashlib.sha256(f"{content_id}|{revision}".encode()).hexdigest()[:12]
    return f"draft-{digest}"


@dataclass
class StructuredDraft:
    draft_id: str
    content_id: str
    content_type: str
    title: str
    summary: str
    sections: list[DraftSection] = field(default_factory=list)
    statements: list[DraftStatement] = field(default_factory=list)
    slug: str = ""
    status: str = "DRAFT"
    repair_attempts: int = 0
    generated_at: str = ""
    generator_provider: str = "mock"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "draft_id": self.draft_id,
            "content_id": self.content_id,
            "content_type": self.content_type,
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "statements": [s.to_dict() for s in self.statements],
            "slug": self.slug,
            "status": self.status,
            "repair_attempts": self.repair_attempts,
            "generated_at": self.generated_at,
            "generator_provider": self.generator_provider,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> StructuredDraft:
        return cls(
            draft_id=str(data.get("draft_id") or ""),
            content_id=str(data.get("content_id") or ""),
            content_type=str(data.get("content_type") or ContentType.DAILY.value),
            title=str(data.get("title") or ""),
            summary=str(data.get("summary") or ""),
            sections=[DraftSection.from_dict(s) for s in (data.get("sections") or [])],
            statements=[DraftStatement.from_dict(s) for s in (data.get("statements") or [])],
            slug=str(data.get("slug") or ""),
            status=str(data.get("status") or "DRAFT"),
            repair_attempts=int(data.get("repair_attempts") or 0),
            generated_at=str(data.get("generated_at") or ""),
            generator_provider=str(data.get("generator_provider") or "mock"),
            metadata=dict(data.get("metadata") or {}),
        )


class ContentGenerator(ABC):
    """Minimal provider abstraction — do not hardcode a vendor SDK into the pipeline."""

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        context: AllowedFactsContext,
        *,
        candidate: ContentCandidate | None = None,
    ) -> StructuredDraft:
        raise NotImplementedError


class MockContentGenerator(ContentGenerator):
    """Deterministic generator for CI / fixtures. Never calls a remote model."""

    name = "mock"

    def __init__(self, *, corrupt: str | None = None) -> None:
        """corrupt: optional injection for negative tests:
        new_fact | new_number | unsupported_entity | causal | pseudo_precision | industry_standard
        """
        self.corrupt = corrupt

    def generate(
        self,
        context: AllowedFactsContext,
        *,
        candidate: ContentCandidate | None = None,
    ) -> StructuredDraft:
        content_id = (candidate.content_id if candidate else "") or f"ct-{context.content_candidate_id}"
        slug = (candidate.slug if candidate else "") or "draft-slug"
        draft_id = make_draft_id(content_id)
        statements: list[DraftStatement] = []
        sections: list[DraftSection] = []

        for claim in context.allowed_claims:
            statements.append(
                DraftStatement(
                    text=claim.text,
                    statement_type="FACT",
                    claim_ids=[claim.claim_id],
                    numeric_kind="SOURCE_FACT" if any(ch.isdigit() for ch in claim.text) else None,
                )
            )
            sections.append(
                DraftSection(title=claim.text[:40], body=claim.text, claim_ids=[claim.claim_id])
            )

        for exp in context.experiment_parameters:
            statements.append(
                DraftStatement(
                    text=str(exp.get("text") or ""),
                    statement_type="EXPERIMENT_PARAMETER",
                    claim_ids=list(exp.get("claim_ids") or []),
                    numeric_kind="EXPERIMENT_PARAMETER",
                    parameter_basis="zerorealm_suggested",
                    zerorealm_suggested=True,
                    industry_standard=False,
                )
            )

        if self.corrupt == "new_fact":
            statements.append(
                DraftStatement(
                    text="某未知机构宣布智能柜渗透率达到历史新高。",
                    statement_type="FACT",
                    claim_ids=[],
                )
            )
        elif self.corrupt == "new_number":
            statements.append(
                DraftStatement(
                    text="智能柜渠道动销提升 37.5%。",
                    statement_type="FACT",
                    claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                )
            )
        elif self.corrupt == "unsupported_entity":
            statements.append(
                DraftStatement(
                    text="星巴克智能柜试点证明无人零售全面爆发。",
                    statement_type="FACT",
                    claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                )
            )
        elif self.corrupt == "causal":
            base = context.allowed_claims[0].text if context.allowed_claims else "营收增长"
            statements.append(
                DraftStatement(
                    text=f"{base}，说明其智能柜渠道动销能力较强。",
                    statement_type="FACT",
                    claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                )
            )
        elif self.corrupt == "pseudo_precision":
            statements.extend(
                [
                    DraftStatement(
                        text="Prediction 70%",
                        statement_type="FACT",
                        claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                    ),
                    DraftStatement(
                        text="趋势★★★★★",
                        statement_type="FACT",
                        claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                    ),
                    DraftStatement(
                        text="连续上涨第10天",
                        statement_type="FACT",
                        claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                    ),
                ]
            )
        elif self.corrupt == "industry_standard":
            statements.append(
                DraftStatement(
                    text="行业标准为10台柜观察7天。",
                    statement_type="FACT",
                    claim_ids=[context.allowed_claims[0].claim_id] if context.allowed_claims else [],
                    numeric_kind="SOURCE_FACT",
                )
            )

        return StructuredDraft(
            draft_id=draft_id,
            content_id=content_id,
            content_type=context.content_type,
            title=context.working_title,
            summary=context.research_question,
            sections=sections,
            statements=statements,
            slug=slug,
            status="DRAFT",
            generated_at=now_iso(),
            generator_provider=self.name,
            metadata={"prompt_rules": GENERATOR_PROMPT_RULES, "corrupt": self.corrupt},
        )


class ConfigurableContentGenerator(ContentGenerator):
    """Production-ready adapter. Without credentials, falls back to mock.

    Set CONTENT_GENERATOR_PROVIDER=mock|openai|gemini (etc).
    Real vendor SDKs are intentionally not imported here for CI safety.
    """

    name = "configurable"

    def __init__(self, *, provider: str | None = None, corrupt: str | None = None) -> None:
        self.provider = (provider or os.getenv("CONTENT_GENERATOR_PROVIDER") or "mock").lower()
        self._mock = MockContentGenerator(corrupt=corrupt)
        self.name = self.provider if self.provider != "configurable" else "mock"

    def generate(
        self,
        context: AllowedFactsContext,
        *,
        candidate: ContentCandidate | None = None,
    ) -> StructuredDraft:
        # Real LLM hooks would go here behind env flags; CI must stay deterministic.
        if self.provider not in {"mock", "", "none"} and os.getenv("CONTENT_GENERATOR_ALLOW_LIVE") == "1":
            raise RuntimeError(
                f"Live generator provider '{self.provider}' is not wired in this build; "
                "use mock or implement a provider adapter."
            )
        draft = self._mock.generate(context, candidate=candidate)
        draft.generator_provider = self.name
        return draft


def get_generator(*, provider: str | None = None, corrupt: str | None = None) -> ContentGenerator:
    return ConfigurableContentGenerator(provider=provider, corrupt=corrupt)


def generate_controlled_draft(
    candidate: ContentCandidate,
    *,
    atom_store: ResearchAtomStore | None = None,
    generator: ContentGenerator | None = None,
    corrupt: str | None = None,
) -> StructuredDraft:
    context = build_allowed_facts(candidate, atom_store=atom_store)
    candidate.metadata["allowed_facts"] = context.to_dict()
    gen = generator or get_generator(corrupt=corrupt)
    draft = gen.generate(context, candidate=candidate)
    # Persist structured draft onto candidate for downstream audit/render.
    candidate.draft = _structured_to_candidate_draft(draft, candidate)
    candidate.metadata["structured_draft"] = draft.to_dict()
    candidate.metadata["draft_id"] = draft.draft_id
    return draft


def _structured_to_candidate_draft(draft: StructuredDraft, candidate: ContentCandidate) -> dict[str, Any]:
    return {
        "draft_id": draft.draft_id,
        "content_id": draft.content_id,
        "content_type": draft.content_type,
        "slug": draft.slug or candidate.slug,
        "title": draft.title,
        "summary": draft.summary,
        "body": "\n\n".join(f"[{s.statement_type}] {s.text}" for s in draft.statements),
        "sections": [
            {
                "level": "core",
                "title": sec.title,
                "excerpt": sec.body,
                "claim_ids": list(sec.claim_ids),
                "source_url": "https://fixture.local/source",
                "source_name": "verified-source",
                "source_type": "web",
            }
            for sec in draft.sections
        ],
        "statements": [s.to_dict() for s in draft.statements],
        "primary_signal": candidate.primary_signal,
        "primary_signal_count": candidate.primary_signal_count,
        "claim_map": {cid: True for cid in candidate.claim_ids},
        "source_map": {
            "source_document_ids": list(candidate.source_document_ids),
            "evidence_ids": list(candidate.evidence_ids),
            "independent_source_count": candidate.independent_source_count,
        },
        "generated_at": draft.generated_at,
        "staging_only": True,
        "wechat_published": False,
        "website_published": False,
        "generator_provider": draft.generator_provider,
    }
