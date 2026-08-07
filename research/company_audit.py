"""Company audit and readiness checks — never auto-approve."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from research.content_lint import lint_company
from research.models import CompanyProfile, SourceDocument


@dataclass
class CompanyAuditRow:
    name: str
    slug: str
    status: str
    source_count: int
    source_types: list[str]
    verified_at: str
    missing_fields: list[str]
    risks: list[str]
    relations: dict
    readiness: str  # READY|NOT_READY|NEEDS_REVIEW
    core_business: str = ""
    summary: str = ""


PRIORITY_NAMES = {
    "友宝",
    "丰e足食",
    "嗨便利",
    "映翰通",
    "云拿",
    "合豚",
    "便利蜂",
    "美团",
    "蛙笑科技",
    "每日优鲜",
}


def missing_fields(company: CompanyProfile) -> list[str]:
    missing = []
    if not company.name.strip():
        missing.append("name")
    if not company.slug.strip():
        missing.append("slug")
    if not company.summary.strip() or "公开图谱收录" in company.summary:
        missing.append("summary")
    if not company.core_business.strip():
        missing.append("coreBusiness")
    if not company.scenarios:
        missing.append("scenarios")
    if not company.verified_at:
        missing.append("verifiedAt")
    return missing


def readiness(
    company: CompanyProfile,
    *,
    sources: list[SourceDocument] | None = None,
) -> str:
    """READY / NOT_READY / NEEDS_REVIEW — not a company score."""
    sources = sources or []
    missing = missing_fields(company)
    lint = lint_company(company)
    errors = [item for item in lint if item.severity == "error"]
    high_sources = [
        source
        for source in sources
        if source.credibility in {"high", "official"} or source.source_type == "official"
    ]
    if company.status == "draft" and missing:
        return "NOT_READY"
    if errors or not high_sources:
        return "NEEDS_REVIEW"
    if company.status in {"approved", "published"} and not missing:
        return "READY"
    return "NEEDS_REVIEW"


def audit_company(
    company: CompanyProfile,
    *,
    sources_by_id: dict[str, SourceDocument] | None = None,
) -> CompanyAuditRow:
    sources_by_id = sources_by_id or {}
    # Companies currently lack direct source_ids; keep count 0 unless wired later.
    related_sources: list[SourceDocument] = []
    missing = missing_fields(company)
    risks = [issue.message for issue in lint_company(company)]
    if company.status == "draft":
        risks.append("仍为 draft，不会进入 Public Bundle")
    return CompanyAuditRow(
        name=company.name,
        slug=company.slug,
        status=company.status,
        source_count=len(related_sources),
        source_types=sorted({source.source_type for source in related_sources}),
        verified_at=company.verified_at,
        missing_fields=missing,
        risks=risks,
        relations={
            "relatedCaseIds": list(company.related_case_ids),
            "relatedSignalIds": list(company.related_signal_ids),
        },
        readiness=readiness(company, sources=related_sources),
        core_business=company.core_business,
        summary=company.summary,
    )


def prioritize_review_queue(rows: list[CompanyAuditRow], limit: int = 10) -> list[CompanyAuditRow]:
    """Recommend first review batch from public catalog signals only."""
    role_bonus = {
        "operator": 3,
        "hardware": 3,
        "software": 2,
        "brand": 1,
        "scenario": 1,
    }

    def score(row: CompanyAuditRow) -> tuple:
        name_hit = 1 if row.name in PRIORITY_NAMES else 0
        richness = 0 if "summary" in row.missing_fields else 1
        role = role_bonus.get(row.core_business, 0)
        smart_cabinetish = 1 if row.core_business in {"operator", "hardware", "software"} else 0
        return (name_hit, smart_cabinetish, role, richness, -len(row.missing_fields))

    ranked = sorted(rows, key=score, reverse=True)
    return ranked[:limit]


def rows_as_dicts(rows: list[CompanyAuditRow]) -> list[dict]:
    return [asdict(row) for row in rows]
