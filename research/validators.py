"""Evidence and claim validation rules for research publishing gates."""

from __future__ import annotations

from dataclasses import dataclass

from research.models import Claim, ClaimStatus, ClaimType, SourceDocument

_FACT_LIKE_OPINION_MARKERS = (
    "必将",
    "一定",
    "肯定会",
    "毫无疑问",
    "已经证明",
    "事实是",
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str  # error | warning
    claim_id: str = ""
    source_id: str = ""


def validate_claim(
    claim: Claim,
    sources: dict[str, SourceDocument],
    claims: dict[str, Claim] | None = None,
) -> list[ValidationIssue]:
    """Validate a single claim against source and review rules."""
    claims = claims or {}
    issues: list[ValidationIssue] = []

    if claim.type is ClaimType.FACT:
        if not claim.source_ids:
            issues.append(
                ValidationIssue(
                    code="FACT_MISSING_SOURCE",
                    message="FACT claims must reference at least one source",
                    severity="error",
                    claim_id=claim.id,
                )
            )
        if claim.status is not ClaimStatus.VERIFIED:
            issues.append(
                ValidationIssue(
                    code="FACT_NOT_VERIFIED",
                    message="FACT claims must be manually verified before publish",
                    severity="error",
                    claim_id=claim.id,
                )
            )

    if claim.type is ClaimType.INFERENCE and not claim.based_on_claim_ids:
        issues.append(
            ValidationIssue(
                code="INFERENCE_MISSING_FACT_BASIS",
                message="INFERENCE claims must cite supporting claim IDs",
                severity="error",
                claim_id=claim.id,
            )
        )
    elif claim.type is ClaimType.INFERENCE:
        for basis_id in claim.based_on_claim_ids:
            basis = claims.get(basis_id)
            if basis is None:
                issues.append(
                    ValidationIssue(
                        code="INFERENCE_MISSING_FACT_BASIS",
                        message=f"INFERENCE cites unknown claim '{basis_id}'",
                        severity="error",
                        claim_id=claim.id,
                    )
                )
            elif basis.type is not ClaimType.FACT:
                issues.append(
                    ValidationIssue(
                        code="INFERENCE_MISSING_FACT_BASIS",
                        message="INFERENCE must be based on FACT claims",
                        severity="error",
                        claim_id=claim.id,
                    )
                )

    if claim.type is ClaimType.OPINION and any(
        marker in claim.text for marker in _FACT_LIKE_OPINION_MARKERS
    ):
        issues.append(
            ValidationIssue(
                code="OPINION_AS_FACT",
                message="OPINION uses deterministic wording that reads like fact",
                severity="warning",
                claim_id=claim.id,
            )
        )

    for source_id in claim.source_ids:
        source = sources.get(source_id)
        if source is None:
            issues.append(
                ValidationIssue(
                    code="SOURCE_MISSING_URL",
                    message=f"claim references unknown source '{source_id}'",
                    severity="error",
                    claim_id=claim.id,
                    source_id=source_id,
                )
            )
            continue
        if not (source.url or "").strip():
            issues.append(
                ValidationIssue(
                    code="SOURCE_MISSING_URL",
                    message="source URL is required",
                    severity="error",
                    claim_id=claim.id,
                    source_id=source.id,
                )
            )
        if not (source.published_at or "").strip():
            issues.append(
                ValidationIssue(
                    code="SOURCE_MISSING_PUBLISHED_AT",
                    message="source published_at is missing",
                    severity="warning",
                    claim_id=claim.id,
                    source_id=source.id,
                )
            )
        if source.credibility == "low" and claim.type is ClaimType.FACT:
            issues.append(
                ValidationIssue(
                    code="LOW_CREDIBILITY_SOURCE",
                    message="low-credibility source cannot support critical FACT",
                    severity="error",
                    claim_id=claim.id,
                    source_id=source.id,
                )
            )

    return issues


def validate_claims(
    claims: list[Claim],
    sources: dict[str, SourceDocument],
) -> list[ValidationIssue]:
    """Validate a claim set; returns all issues (errors and warnings)."""
    claim_map = {claim.id: claim for claim in claims}
    issues: list[ValidationIssue] = []
    for claim in claims:
        issues.extend(validate_claim(claim, sources=sources, claims=claim_map))
    return issues


#: Codes that block *publishing* but must not block Discovery intake.
#: Candidate VERIFIED means the source is research-eligible evidence material;
#: it does **not** mean a human finished ClaimStatus.VERIFIED review.
DISCOVERY_NON_BLOCKING_CODES = frozenset({"FACT_NOT_VERIFIED"})


def validate_discovery_atoms(
    claims: list[Claim],
    sources: dict[str, SourceDocument],
) -> list[ValidationIssue]:
    """Research validators for Discovery eligibility (excludes publish-only codes)."""
    return [
        issue
        for issue in validate_claims(claims, sources)
        if issue.code not in DISCOVERY_NON_BLOCKING_CODES
    ]


def has_blocking_issues(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
