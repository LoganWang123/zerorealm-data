"""Content linter for research catalog — report only, never auto-fix."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from research.models import CaseStudy, CompanyProfile, MetricDefinition

MARKETING = ("赋能", "颠覆", "引领未来", "全方位", "一站式解决方案")
ABSOLUTES = ("行业第一", "全球第一", "最大", "唯一", "领先", "最强")
NUMBER = re.compile(r"\d+(?:\.\d+)?%?|\d+万|\d+亿")


@dataclass
class LintIssue:
    code: str
    severity: str  # error|warning|info
    message: str
    entity_type: str
    entity_id: str


def lint_company(company: CompanyProfile) -> list[LintIssue]:
    issues: list[LintIssue] = []
    text = f"{company.summary} {company.business_model}"
    if not company.summary.strip():
        issues.append(_issue("EMPTY_SUMMARY", "error", "summary 为空", "company", company.id))
    if not company.core_business.strip():
        issues.append(
            _issue("MISSING_CORE_BUSINESS", "error", "coreBusiness 为空", "company", company.id)
        )
    if not company.scenarios:
        issues.append(_issue("MISSING_SCENARIOS", "warning", "scenarios 为空", "company", company.id))
    if not company.verified_at and company.status in {"approved", "published"}:
        issues.append(
            _issue("MISSING_VERIFIED_AT", "error", "已批准但无 verifiedAt", "company", company.id)
        )
    for token in MARKETING:
        if token in text:
            issues.append(
                _issue("MARKETING_LANGUAGE", "warning", f"疑似营销词: {token}", "company", company.id)
            )
    for token in ABSOLUTES:
        if token in text:
            issues.append(
                _issue("ABSOLUTE_CLAIM", "error", f"绝对化表述: {token}", "company", company.id)
            )
    if NUMBER.search(text) and not company.verified_at:
        issues.append(
            _issue(
                "NUMBER_WITHOUT_YEAR_OR_SOURCE",
                "warning",
                "摘要含数字但缺少核验时间/来源绑定",
                "company",
                company.id,
            )
        )
    if "公开图谱收录" in company.summary:
        issues.append(
            _issue("THIN_BOOTSTRAP_SUMMARY", "info", "摘要仍为图谱引导语", "company", company.id)
        )
    return issues


def lint_case(case: CaseStudy) -> list[LintIssue]:
    issues: list[LintIssue] = []
    if not case.limitations:
        issues.append(
            _issue("CASE_MISSING_LIMITATIONS", "error", "案例缺少 limitations", "case", case.id)
        )
    joined = f"{case.problem} {case.solution} {case.how_it_works}"
    for token in ABSOLUTES:
        if token in joined:
            issues.append(
                _issue("ABSOLUTE_CLAIM", "error", f"绝对化表述: {token}", "case", case.id)
            )
    return issues


def lint_metric(metric: MetricDefinition) -> list[LintIssue]:
    issues: list[LintIssue] = []
    if not metric.common_pitfalls:
        issues.append(
            _issue("METRIC_MISSING_PITFALLS", "error", "指标缺少 commonPitfalls", "metric", metric.id)
        )
    if not metric.definition.strip():
        issues.append(_issue("EMPTY_DEFINITION", "error", "definition 为空", "metric", metric.id))
    return issues


def lint_catalog(companies, cases, metrics) -> list[dict]:
    issues: list[LintIssue] = []
    for company in companies:
        issues.extend(lint_company(company))
    for case in cases:
        issues.extend(lint_case(case))
    for metric in metrics:
        issues.extend(lint_metric(metric))
    return [asdict(item) for item in issues]


def _issue(code: str, severity: str, message: str, entity_type: str, entity_id: str) -> LintIssue:
    return LintIssue(
        code=code,
        severity=severity,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
