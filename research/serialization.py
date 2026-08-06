"""Public Bundle v1 serialization with explicit field whitelists."""

from __future__ import annotations

from research.models import (
    CaseStudy,
    Claim,
    CompanyProfile,
    IndustrySignal,
    MetricDefinition,
    SourceDocument,
    Topic,
)

FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "reviewNote",
        "review_note",
        "rawExcerpt",
        "raw_excerpt",
        "fetchedAt",
        "fetched_at",
        "evidenceIds",
        "evidence_ids",
        "prompt",
        "modelResponse",
        "model_response",
        "apiKey",
        "api_key",
        "secret",
        "artifactPath",
        "artifact_path",
        "reviewedAt",
        "reviewed_at",
        "status",
    }
)


def _sorted_ids(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return sorted({value for value in (values or []) if value})


def serialize_source(source: SourceDocument) -> dict:
    """PublicSource whitelist."""
    return {
        "id": source.id,
        "url": source.url,
        "title": source.title,
        "sourceName": source.source_name,
        "publishedAt": source.published_at,
        "credibility": source.credibility,
    }


def serialize_claim(claim: Claim) -> dict:
    """PublicClaim whitelist."""
    return {
        "id": claim.id,
        "text": claim.text,
        "type": claim.type.value if hasattr(claim.type, "value") else str(claim.type),
        "confidence": (
            claim.confidence.value
            if hasattr(claim.confidence, "value")
            else str(claim.confidence)
        ),
        "sourceIds": _sorted_ids(claim.source_ids),
        "basedOnClaimIds": _sorted_ids(claim.based_on_claim_ids),
    }


def serialize_signal(signal: IndustrySignal) -> dict:
    """IndustrySignal public object whitelist."""
    return {
        "id": signal.id,
        "slug": signal.slug,
        "title": signal.title,
        "summary": signal.summary,
        "whyItMatters": signal.why_it_matters,
        "affectedRoles": _sorted_ids(list(signal.affected_roles)),
        "judgment": signal.judgment,
        "claimIds": _sorted_ids(signal.claim_ids),
        "sourceIds": _sorted_ids(signal.source_ids),
        "companyIds": _sorted_ids(signal.company_ids),
        "verificationStatus": signal.verification_status,
        "publishedAt": signal.published_at,
        "tags": _sorted_ids(list(signal.tags)),
    }


def serialize_company(company: CompanyProfile) -> dict:
    return {
        "id": company.id,
        "slug": company.slug,
        "name": company.name,
        "summary": company.summary,
        "coreBusiness": company.core_business,
        "products": sorted(company.products),
        "scenarios": sorted(company.scenarios),
        "businessModel": company.business_model,
        "relatedCaseIds": _sorted_ids(company.related_case_ids),
        "relatedSignalIds": _sorted_ids(company.related_signal_ids),
        "verifiedAt": company.verified_at,
    }


def serialize_case(case: CaseStudy) -> dict:
    return {
        "id": case.id,
        "slug": case.slug,
        "title": case.title,
        "problem": case.problem,
        "solution": case.solution,
        "howItWorks": case.how_it_works,
        "publicResults": list(case.public_results),
        "limitations": list(case.limitations),
        "companyIds": _sorted_ids(case.company_ids),
    }


def serialize_metric(metric: MetricDefinition) -> dict:
    return {
        "id": metric.id,
        "slug": metric.slug,
        "name": metric.name,
        "definition": metric.definition,
        "formula": metric.formula,
        "applicableScenarios": sorted(metric.applicable_scenarios),
        "commonPitfalls": list(metric.common_pitfalls),
        "relatedCaseIds": _sorted_ids(metric.related_case_ids),
    }


def serialize_topic(topic: Topic) -> dict:
    return {
        "id": topic.id,
        "slug": topic.slug,
        "title": topic.title,
        "summary": topic.summary,
        "signalIds": _sorted_ids(topic.signal_ids),
        "companyIds": _sorted_ids(topic.company_ids),
        "caseIds": _sorted_ids(topic.case_ids),
        "metricIds": _sorted_ids(topic.metric_ids),
    }
