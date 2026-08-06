"""ResearchPublishService — validate research then publish via existing workflow."""

from __future__ import annotations

from dataclasses import dataclass, field

from publishing.adapters.research_to_article import research_brief_to_article
from publishing.models import ChannelTarget, PublishResult, RenderContext
from publishing.workflow import PublishWorkflow
from research.models import (
    CaseStudy,
    Claim,
    ClaimStatus,
    ClaimType,
    IndustrySignal,
    ResearchBrief,
    SourceDocument,
)
from research.validators import ValidationIssue, has_blocking_issues, validate_claims


class ResearchPublishError(ValueError):
    """Raised when research content cannot be published."""


@dataclass
class ResearchPublishRequest:
    brief: ResearchBrief
    claims: dict[str, Claim] = field(default_factory=dict)
    sources: dict[str, SourceDocument] = field(default_factory=dict)
    signals: list[IndustrySignal] = field(default_factory=list)
    cases: list[CaseStudy] = field(default_factory=list)
    template: str = "deep_insight"
    issue: int = 0
    date: str = ""


class ResearchPublishService:
    """Evidence gate + Adapter + PublishWorkflow.run_article()."""

    ALLOWED_TEMPLATES = frozenset(
        {"signal_digest", "deep_insight", "case_study", "company_profile"}
    )

    def __init__(self, workflow: PublishWorkflow):
        self.workflow = workflow

    def validate(self, request: ResearchPublishRequest) -> list[ValidationIssue]:
        if request.brief.status not in {"approved", "published"}:
            return [
                ValidationIssue(
                    code="BRIEF_NOT_APPROVED",
                    message=f"brief status '{request.brief.status}' is not exportable",
                    severity="error",
                )
            ]
        if request.template not in self.ALLOWED_TEMPLATES:
            return [
                ValidationIssue(
                    code="UNKNOWN_TEMPLATE",
                    message=f"unsupported template '{request.template}'",
                    severity="error",
                )
            ]

        selected_claims = [
            request.claims[claim_id]
            for claim_id in request.brief.claim_ids
            if claim_id in request.claims
        ]
        missing = [cid for cid in request.brief.claim_ids if cid not in request.claims]
        issues: list[ValidationIssue] = [
            ValidationIssue(
                code="BROKEN_REFERENCE",
                message=f"brief references missing claim '{cid}'",
                severity="error",
                claim_id=cid,
            )
            for cid in missing
        ]
        for claim in selected_claims:
            if claim.status is not ClaimStatus.VERIFIED:
                issues.append(
                    ValidationIssue(
                        code="FACT_NOT_VERIFIED"
                        if claim.type is ClaimType.FACT
                        else "CLAIM_NOT_VERIFIED",
                        message=f"claim '{claim.id}' is not verified",
                        severity="error",
                        claim_id=claim.id,
                    )
                )
        issues.extend(validate_claims(selected_claims, request.sources))
        return issues

    def publish(
        self,
        request: ResearchPublishRequest,
        target: ChannelTarget,
        context: RenderContext,
        mode: str = "draft",
    ) -> PublishResult:
        issues = self.validate(request)
        if has_blocking_issues(issues):
            codes = ", ".join(sorted({issue.code for issue in issues if issue.severity == "error"}))
            raise ResearchPublishError(f"research publish blocked: {codes}")

        article = research_brief_to_article(
            request.brief,
            signals=request.signals,
            cases=request.cases,
            issue=request.issue,
            date=request.date,
            template=request.template,
        )
        return self.workflow.run_article(article, target, context, mode=mode)
