"""Production Editorial Hard Gate — heuristic pre-publish scanners for Daily content.

Context: production has shipped daily digests that violate the
single-signal-daily policy, present pseudo-precise predictions with no
disclosed methodology, or stretch a single company's financial results into
channel-/market-wide claims. This module is a deliberately *heuristic*
(regex + structural) gate that runs on the raw report/MDX frontmatter dict
BEFORE a channel renders or publishes it, so those patterns get caught
mechanically instead of relying solely on human review.

The gate is not a semantic fact-checker. It looks for known-bad textual and
structural patterns and fails closed. Human editorial review remains the
final arbiter for anything the heuristics don't catch — see
``docs/reports/production-editorial-audit-2026-08-08.md`` for the audit that
motivated this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------


class EditorialGateErrorCode:
    """Canonical error/warning codes emitted by the hard gate."""

    MULTI_SIGNAL_DAILY = "MULTI_SIGNAL_DAILY"
    UNSUPPORTED_CHANNEL_INFERENCE = "UNSUPPORTED_CHANNEL_INFERENCE"
    CLAIM_EVIDENCE_CONTRADICTION = "CLAIM_EVIDENCE_CONTRADICTION"
    METRIC_DIMENSION_MISMATCH = "METRIC_DIMENSION_MISMATCH"
    UNLABELED_EXPERIMENT_PARAMETER = "UNLABELED_EXPERIMENT_PARAMETER"
    UNSUPPORTED_THRESHOLD = "UNSUPPORTED_THRESHOLD"
    PSEUDO_PRECISION = "PSEUDO_PRECISION"
    SOURCE_LINEAGE_INCOMPLETE = "SOURCE_LINEAGE_INCOMPLETE"
    UNSOURCED_PREDICTION = "UNSOURCED_PREDICTION"
    UNSUPPORTED_NUMERIC_CLAIM = "UNSUPPORTED_NUMERIC_CLAIM"
    UNSUPPORTED_SAMPLE = "UNSUPPORTED_SAMPLE"
    SINGLE_COMPANY_MARKET_GENERALIZATION = "SINGLE_COMPANY_MARKET_GENERALIZATION"
    OVERGENERALIZED_HEADLINE = "OVERGENERALIZED_HEADLINE"
    INTERNAL_COPY_EXPOSED = "INTERNAL_COPY_EXPOSED"
    FABRICATED_DATA = "FABRICATED_DATA"
    FUTURE_PUBLICATION = "FUTURE_PUBLICATION"
    UNSUPPORTED_FACT = "UNSUPPORTED_FACT"
    RESEARCH_COUNT_INCONSISTENT = "RESEARCH_COUNT_INCONSISTENT"
    SEARCH_SNIPPET_AS_EVIDENCE = "SEARCH_SNIPPET_AS_EVIDENCE"
    UNSUPPORTED_CAUSAL_INFERENCE = "UNSUPPORTED_CAUSAL_INFERENCE"
    STALE_PRIMARY_SIGNAL = "STALE_PRIMARY_SIGNAL"
    CONTENT_TYPE_MISMATCH = "CONTENT_TYPE_MISMATCH"
    CLAIM_NOT_VERIFIED = "CLAIM_NOT_VERIFIED"
    ORPHAN_FACT = "ORPHAN_FACT"
    UNSUPPORTED_ENTITY = "UNSUPPORTED_ENTITY"
    CHANNEL_REVIEW_REQUIRED = "CHANNEL_REVIEW_REQUIRED"


ALL_ERROR_CODES = frozenset(
    value
    for name, value in vars(EditorialGateErrorCode).items()
    if not name.startswith("_") and isinstance(value, str)
)

#: Errors that a signed-off ``editorial_exception`` can never waive, even with
#: a reason + approved_at. These represent trust/safety-critical failures.
NON_BYPASSABLE_ERROR_CODES = frozenset(
    {
        EditorialGateErrorCode.UNSUPPORTED_FACT,
        EditorialGateErrorCode.SOURCE_LINEAGE_INCOMPLETE,
        EditorialGateErrorCode.FABRICATED_DATA,
        EditorialGateErrorCode.FUTURE_PUBLICATION,
        EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE,
        EditorialGateErrorCode.CLAIM_NOT_VERIFIED,
        EditorialGateErrorCode.ORPHAN_FACT,
        EditorialGateErrorCode.UNSUPPORTED_ENTITY,
    }
)

_SEARCH_SNIPPET_SOURCE_TYPES = frozenset(
    {
        "search_snippet",
        "anysearch_snippet",
        "provider_content",
        "search_preview",
    }
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class GateIssue:
    """A single error/warning raised by a scanner."""

    code: str
    message: str
    location: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        suffix = f" [{self.location}]" if self.location else ""
        return f"{self.code}: {self.message}{suffix}"

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "location": self.location}


@dataclass
class EditorialGateResult:
    """Outcome of :func:`run_daily_editorial_gate`."""

    status: str = "passed"  # "passed" | "failed"
    errors: list[GateIssue] = field(default_factory=list)
    warnings: list[GateIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def error_codes(self) -> list[str]:
        return [issue.code for issue in self.errors]

    @property
    def warning_codes(self) -> list[str]:
        return [issue.code for issue in self.warnings]

    def has_error(self, code: str) -> bool:
        return code in self.error_codes

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


# ---------------------------------------------------------------------------
# Shared textual markers
# ---------------------------------------------------------------------------

# Explicit labels that mark a numeric parameter as a non-binding suggestion
# rather than an unsupported universal rule.
LABEL_MARKERS = (
    "建议起点",
    "建议试验起点",
    "示例试验",
    "企业自定义",
    "参考起点",
    "示例参数",
    "非行业标准",
    "仅供参考",
    "按企业实际",
)

# Observational lookback windows inside Decision cards (not experiment scale claims).
OBSERVATIONAL_LOOKBACK_PATTERN = re.compile(
    r"(?:近|最近|过去|连续|观察)\s*\d+\s*天"
)

# Phrases that disclose the statistical/experimental basis for a number,
# satisfying the "methodology disclosed" bar for predictions/pseudo precision.
METHODOLOGY_MARKERS = (
    "样本",
    "抽样",
    "统计口径",
    "方法论",
    "回测",
    "随机实验",
    "对照组",
    "实验组",
    "置信区间",
) + LABEL_MARKERS

# Hedge phrases that explicitly disclaim over-generalizing a single data point.
HEDGE_MARKERS = (
    "不能直接证明",
    "不代表",
    "不等于",
    "因地制宜",
    "不能替代",
    "不能简单视为",
    "不应预设",
    "需结合自身",
    "按自身口径",
    "不预设",
    "仅作为",
    "不是普遍发生",
)

CHANNEL_INFERENCE_PHRASES = (
    "渠道动销",
    "终端动销",
    "渠道加速",
    "终端旺销",
    "渠道走强",
    "动销加速",
    "全渠道热销",
    "渠道回暖",
    "渠道全面走强",
    "终端全面动销",
)

MARKET_GENERALIZATION_PHRASES = (
    "全行业",
    "行业整体",
    "市场普遍",
    "所有柜机",
    "全国范围内",
    "整个行业",
    "全网",
    "整个市场",
    "所有运营商",
)

UNDISCLOSED_MARKERS = (
    "未披露",
    "暂无",
    "尚未公开",
    "数据未公开",
    "未公开",
    "尚未披露",
)

INTERNAL_MARKERS = (
    "todo",
    "fixme",
    "内部草稿",
    "占位内容",
    "测试占位",
    "placeholder",
    "草稿勿发",
    "请勿外发",
    "xxx请补充",
)

FACT_MARKERS = (
    "据统计",
    "据了解",
    "数据显示",
    "报告显示",
    "研究显示",
    "研究发现",
)

SCALE_CONTEXT_MARKERS = (
    "覆盖",
    "共有",
    "总计",
    "随机实验",
    "研究团队",
    "研究覆盖",
    "研究了",
)

COMPANY_GROWTH_PATTERN = re.compile(
    r"(营收|营业收入|收入|净利润|归母净利润|净利)[^。\n]{0,20}(同比)?(增长|增加)\s*\d+(\.\d+)?\s*%"
)
COUNT_PARAM_PATTERN = re.compile(r"\d+\s*台|\d+\s*天|\d+\s*个百分点|\d+\s*名")
THRESHOLD_PATTERN = re.compile(
    r"毛利(率)?(低于|不足)\s*\d+(\.\d+)?%"
    r"|缺货率(超过|高于)\s*\d+(\.\d+)?%"
    r"|动销率(低于|不足)\s*\d+(\.\d+)?%"
    r"|(低于|不足|超过|高于)\s*\d+(\.\d+)?%"
)
NUMERIC_CLAIM_PATTERN = re.compile(r"\d+(\.\d+)?\s*(%|亿元|万元|台|个SKU)")


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize_sections(data: dict) -> list[dict]:
    """Flatten V3 (type+items) and V4 (flat, level-tagged) section formats."""
    raw = data.get("sections")
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if "items" in entry and "type" in entry:
            level = entry.get("level", "")
            for item in entry.get("items") or []:
                if isinstance(item, dict):
                    merged = dict(item)
                    merged.setdefault("level", level)
                    result.append(merged)
        else:
            result.append(entry)
    return result


def _decision_blocks(data: dict) -> dict:
    decision = data.get("decision")
    return decision if isinstance(decision, dict) else {}


def _full_text(data: dict, sections: list[dict]) -> str:
    parts: list[str] = []

    title = data.get("title") or data.get("wechat_title")
    if isinstance(title, str):
        parts.append(title)
    if isinstance(data.get("signal"), str):
        parts.append(data["signal"])
    for key in ("discussion", "opportunity", "risk", "counter_view", "trend"):
        value = data.get(key)
        if isinstance(value, str):
            parts.append(value)

    summary = data.get("summary")
    if isinstance(summary, list):
        parts.extend(str(s) for s in summary if isinstance(s, str))

    tomorrow = data.get("tomorrow")
    if isinstance(tomorrow, list):
        parts.extend(str(t) for t in tomorrow if isinstance(t, str))

    for sec in sections:
        for key in ("title", "excerpt", "insight", "spread_line", "verdict"):
            value = sec.get(key)
            if isinstance(value, str):
                parts.append(value)

    for block in _decision_blocks(data).values():
        if isinstance(block, dict):
            for value in block.values():
                if isinstance(value, str):
                    parts.append(value)

    alpha = data.get("alpha")
    if isinstance(alpha, dict):
        for value in alpha.values():
            if isinstance(value, str):
                parts.append(value)

    return "\n".join(parts)


def _has_evidence(block: dict) -> bool:
    evidence = block.get("evidence")
    if isinstance(evidence, list) and any(str(e).strip() for e in evidence):
        return True
    if isinstance(evidence, str) and evidence.strip():
        return True
    basis = block.get("basis")
    if isinstance(basis, str) and basis.strip():
        return True
    return False


def _has_methodology_marker(block: dict) -> bool:
    text_parts: list[str] = []
    for key in ("evidence", "basis", "watch", "confidence_basis", "methodology"):
        value = block.get(key)
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, list):
            text_parts.extend(str(v) for v in value)
    combined = " ".join(text_parts)
    return any(marker in combined for marker in METHODOLOGY_MARKERS)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


# ---------------------------------------------------------------------------
# Individual scanners
# ---------------------------------------------------------------------------


def _check_multi_signal_daily(data: dict, sections: list[dict], errors: list[GateIssue]) -> None:
    core_sections = [s for s in sections if str(s.get("level") or "").strip() == "core"]
    if len(core_sections) > 1:
        errors.append(
            GateIssue(
                EditorialGateErrorCode.MULTI_SIGNAL_DAILY,
                f"Daily contains {len(core_sections)} core signals; "
                "single-signal-daily policy allows exactly one.",
                location="sections",
            )
        )

    primary_count = data.get("primary_signal_count")
    if isinstance(primary_count, int) and primary_count > 1:
        errors.append(
            GateIssue(
                EditorialGateErrorCode.MULTI_SIGNAL_DAILY,
                f"primary_signal_count={primary_count} exceeds the single-signal-daily policy.",
                location="primary_signal_count",
            )
        )


def _check_prediction_block(block: dict, location: str, errors: list[GateIssue]) -> None:
    if not isinstance(block, dict):
        return
    confidence_pct = block.get("confidence_pct")
    has_pct = isinstance(confidence_pct, (int, float)) and confidence_pct not in (None, False)
    if not has_pct:
        return
    if not _has_evidence(block):
        errors.append(
            GateIssue(
                EditorialGateErrorCode.UNSOURCED_PREDICTION,
                f"confidence_pct={confidence_pct} disclosed without evidence/basis.",
                location=location,
            )
        )
    if not _has_methodology_marker(block):
        errors.append(
            GateIssue(
                EditorialGateErrorCode.PSEUDO_PRECISION,
                f"confidence_pct={confidence_pct} presented without disclosed statistical methodology.",
                location=location,
            )
        )


def _check_predictions_and_precision(
    data: dict, sections: list[dict], errors: list[GateIssue]
) -> None:
    _check_prediction_block(data.get("prediction"), "prediction", errors)

    for idx, sec in enumerate(sections):
        _check_prediction_block(sec.get("prediction"), f"sections[{idx}].prediction", errors)

    for role, block in _decision_blocks(data).items():
        _check_prediction_block(block, f"decision.{role}", errors)

    trend = data.get("trend")
    if isinstance(trend, list) and trend:
        has_pseudo_metrics = any(
            isinstance(item, dict) and "stars" in item and "streak" in item for item in trend
        )
        has_methodology = isinstance(data.get("trend_methodology"), str) and _contains_any(
            data["trend_methodology"], METHODOLOGY_MARKERS
        )
        if has_pseudo_metrics and not has_methodology:
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.PSEUDO_PRECISION,
                    "trend uses star ratings + streak counters without disclosed methodology "
                    "(add trend_methodology or drop the pseudo-precise fields).",
                    location="trend",
                )
            )


def _check_channel_inference(full_text: str, errors: list[GateIssue]) -> None:
    if (
        COMPANY_GROWTH_PATTERN.search(full_text)
        and _contains_any(full_text, CHANNEL_INFERENCE_PHRASES)
        and not _contains_any(full_text, HEDGE_MARKERS)
    ):
        errors.append(
            GateIssue(
                EditorialGateErrorCode.UNSUPPORTED_CHANNEL_INFERENCE,
                "Company financial growth is used to infer channel/终端动销 strength "
                "without disclosed channel-level data or a hedge disclaimer.",
                location="body",
            )
        )


def _check_claim_evidence_contradiction(data: dict, full_text: str, errors: list[GateIssue]) -> None:
    tomorrow = data.get("tomorrow")
    tomorrow_text = " ".join(str(t) for t in tomorrow if isinstance(t, str)) if isinstance(tomorrow, list) else ""
    if not tomorrow_text:
        return
    mentions_undisclosed_channel_data = "渠道" in tomorrow_text and _contains_any(
        tomorrow_text, UNDISCLOSED_MARKERS
    )
    if not mentions_undisclosed_channel_data:
        return
    asserts_channel_strength = _contains_any(full_text, CHANNEL_INFERENCE_PHRASES)
    if asserts_channel_strength and not _contains_any(full_text, HEDGE_MARKERS):
        errors.append(
            GateIssue(
                EditorialGateErrorCode.CLAIM_EVIDENCE_CONTRADICTION,
                "tomorrow discloses that channel data is not yet released, "
                "while the body asserts channel strength as settled fact.",
                location="tomorrow",
            )
        )


def _check_metric_dimension_mismatch(data: dict, full_text: str, errors: list[GateIssue]) -> None:
    for role, block in _decision_blocks(data).items():
        if not isinstance(block, dict):
            continue
        evidence = str(block.get("evidence", ""))
        metric = str(block.get("metric", ""))
        if COMPANY_GROWTH_PATTERN.search(evidence) and "动销率" in metric:
            if not _contains_any(full_text, HEDGE_MARKERS):
                errors.append(
                    GateIssue(
                        EditorialGateErrorCode.METRIC_DIMENSION_MISMATCH,
                        f"decision.{role} evidence cites company-level revenue/profit growth "
                        "but metric targets SKU-level 动销率 without disclaiming the dimension "
                        "mismatch (company financials vs. per-SKU channel movement).",
                        location=f"decision.{role}",
                    )
                )


def _check_experiment_params(
    data: dict, sections: list[dict], full_text: str, errors: list[GateIssue]
) -> None:
    already_labeled_globally = _contains_any(full_text, LABEL_MARKERS)

    def _scan(text: str, location: str) -> None:
        if not text:
            return
        locally_labeled = already_labeled_globally or _contains_any(text, LABEL_MARKERS)
        # Strip observational lookbacks ("近7天报表") before judging experiment scale.
        cleaned = OBSERVATIONAL_LOOKBACK_PATTERN.sub(" ", text)
        if COUNT_PARAM_PATTERN.search(cleaned) and not locally_labeled:
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.UNLABELED_EXPERIMENT_PARAMETER,
                    "Experiment scale parameter (N台/N天/N个百分点/N名) is presented as a "
                    "universal rule without a '建议起点/示例试验/企业自定义' label.",
                    location=location,
                )
            )
        if THRESHOLD_PATTERN.search(text) and not locally_labeled:
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.UNSUPPORTED_THRESHOLD,
                    "Numeric threshold (e.g. 毛利低于N%/缺货率超过N%) is presented as a fixed "
                    "rule without a '建议起点/示例试验/企业自定义' label.",
                    location=location,
                )
            )

    for idx, sec in enumerate(sections):
        text = " ".join(
            str(sec.get(k, "")) for k in ("verdict", "insight", "excerpt", "spread_line")
        )
        _scan(text, f"sections[{idx}]")

    for role, block in _decision_blocks(data).items():
        if not isinstance(block, dict):
            continue
        # sample/metric are structural Decision fields: sample is the editorial
        # experiment window by design; metric names the KPI. Hard-fail only on
        # action/kpi/stop_condition copy that asserts unlabeled operating rules.
        text = " ".join(
            str(block.get(k, "")) for k in ("action", "kpi", "stop_condition")
        )
        _scan(text, f"decision.{role}")


def _check_source_lineage(sections: list[dict], errors: list[GateIssue]) -> None:
    for idx, sec in enumerate(sections):
        level = str(sec.get("level") or "").strip()
        if level in ("core", "quick") and not str(sec.get("source_url") or "").strip():
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.SOURCE_LINEAGE_INCOMPLETE,
                    f"{level} item is missing source_url.",
                    location=f"sections[{idx}].source_url",
                )
            )


def _check_headline(title: str, errors: list[GateIssue]) -> None:
    if title and "证明" in title:
        errors.append(
            GateIssue(
                EditorialGateErrorCode.OVERGENERALIZED_HEADLINE,
                "Headline uses an absolute-generalization marker ('证明') for what is a "
                "single data point or small sample.",
                location="title",
            )
        )


def _check_single_company_market_generalization(full_text: str, errors: list[GateIssue]) -> None:
    if (
        COMPANY_GROWTH_PATTERN.search(full_text)
        and _contains_any(full_text, MARKET_GENERALIZATION_PHRASES)
        and not _contains_any(full_text, HEDGE_MARKERS)
    ):
        errors.append(
            GateIssue(
                EditorialGateErrorCode.SINGLE_COMPANY_MARKET_GENERALIZATION,
                "A single company's financial results are generalized into an "
                "industry-/market-wide claim without a hedge disclaimer.",
                location="body",
            )
        )


def _check_internal_copy_exposed(full_text: str, errors: list[GateIssue]) -> None:
    lowered = full_text.lower()
    if any(marker in lowered for marker in INTERNAL_MARKERS):
        errors.append(
            GateIssue(
                EditorialGateErrorCode.INTERNAL_COPY_EXPOSED,
                "Internal placeholder/draft marker detected in publish-bound copy.",
                location="body",
            )
        )


def _check_fabricated_data(data: dict, errors: list[GateIssue]) -> None:
    if data.get("fabricated") is True or str(data.get("data_provenance", "")).strip().lower() == "fabricated":
        errors.append(
            GateIssue(
                EditorialGateErrorCode.FABRICATED_DATA,
                "Content is explicitly flagged as fabricated/invented data.",
                location="data_provenance",
            )
        )


def _check_future_publication(data: dict, errors: list[GateIssue], *, now: date | None = None) -> None:
    raw_date = data.get("date")
    if not raw_date:
        return
    try:
        parsed = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return
    reference = now or date.today()
    if parsed > reference:
        errors.append(
            GateIssue(
                EditorialGateErrorCode.FUTURE_PUBLICATION,
                f"date={raw_date} is in the future relative to {reference.isoformat()}.",
                location="date",
            )
        )


def _check_search_snippet_as_evidence(
    data: dict, sections: list[dict], errors: list[GateIssue]
) -> None:
    """Hard-fail when a claim/section is backed only by search snippet provenance."""

    def _is_snippet_type(value: object) -> bool:
        return str(value or "").strip().lower() in _SEARCH_SNIPPET_SOURCE_TYPES

    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        if _is_snippet_type(section.get("source_type")) or _is_snippet_type(
            section.get("evidence_source_type")
        ):
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE,
                    "Search snippet / provider_content cannot serve as claim evidence.",
                    location=f"sections[{idx}]",
                )
            )

    for key in ("evidence", "claims", "sources"):
        entries = data.get(key)
        if not isinstance(entries, list):
            continue
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            if _is_snippet_type(entry.get("source_type")) or _is_snippet_type(
                entry.get("evidence_source_type")
            ):
                errors.append(
                    GateIssue(
                        EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE,
                        "Search snippet / provider_content cannot serve as claim evidence.",
                        location=f"{key}[{idx}]",
                    )
                )


def _check_unsupported_fact(data: dict, sections: list[dict], full_text: str, errors: list[GateIssue]) -> None:
    has_any_source = bool(str(data.get("source_url") or "").strip()) or any(
        str(sec.get("source_url") or "").strip() for sec in sections
    )
    if _contains_any(full_text, FACT_MARKERS) and not has_any_source:
        errors.append(
            GateIssue(
                EditorialGateErrorCode.UNSUPPORTED_FACT,
                "Factual claim markers (据统计/数据显示/...) present but no source_url is "
                "disclosed anywhere in the daily.",
                location="global",
            )
        )


def _check_unsupported_numeric_claim(sections: list[dict], errors: list[GateIssue]) -> None:
    for idx, sec in enumerate(sections):
        text = " ".join(str(sec.get(k, "")) for k in ("excerpt", "insight"))
        if not text:
            continue
        has_source = bool(str(sec.get("source_url") or "").strip()) or bool(
            str(sec.get("source_name") or "").strip()
        )
        if NUMERIC_CLAIM_PATTERN.search(text) and not has_source:
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM,
                    "Numeric claim present without any source_url/source_name attribution.",
                    location=f"sections[{idx}]",
                )
            )


def _check_unsupported_sample(data: dict, errors: list[GateIssue]) -> None:
    for key in ("alpha", "exclusive_data"):
        block = data.get(key)
        if isinstance(block, dict) and str(block.get("sample") or "").strip() and not str(
            block.get("source") or ""
        ).strip():
            errors.append(
                GateIssue(
                    EditorialGateErrorCode.UNSUPPORTED_SAMPLE,
                    f"{key}.sample is claimed without a disclosed {key}.source.",
                    location=key,
                )
            )


def _check_research_count_consistency(
    sections: list[dict], warnings: list[GateIssue]
) -> None:
    """Flag mixed research-vs-sample scales as warnings only.

    A paper's N (e.g. 59,000台) next to an editorial sample (20台) is common and
    valid; treating it as a hard failure blocks PASS_WITH_EDIT dailies. Keep the
    signal as a warning for human review.
    """
    for idx, sec in enumerate(sections):
        text = " ".join(str(sec.get(k, "")) for k in ("title", "excerpt", "insight"))
        if not _contains_any(text, SCALE_CONTEXT_MARKERS):
            continue
        for unit in ("台", "名", "个SKU"):
            raw_numbers = re.findall(rf"([\d,]+)\s*{re.escape(unit)}", text)
            values = set()
            for raw in raw_numbers:
                try:
                    values.add(int(raw.replace(",", "")))
                except ValueError:
                    continue
            if len(values) > 1:
                warnings.append(
                    GateIssue(
                        EditorialGateErrorCode.RESEARCH_COUNT_INCONSISTENT,
                        f"Inconsistent {unit} counts within the same research claim: "
                        f"{sorted(values)}.",
                        location=f"sections[{idx}]",
                    )
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_daily_editorial_gate(
    report_or_mdx_data: dict, *, now: date | None = None
) -> EditorialGateResult:
    """Run every heuristic scanner against a Daily report/MDX frontmatter dict.

    ``report_or_mdx_data`` is the parsed YAML frontmatter (or equivalent
    report dict) — the same shape produced by
    ``publishing.website.mdx_adapter.extract_frontmatter`` or the LLM daily
    report generator. Returns an :class:`EditorialGateResult`; ``status`` is
    ``"failed"`` whenever any scanner appends an error.
    """
    data = report_or_mdx_data if isinstance(report_or_mdx_data, dict) else {}
    errors: list[GateIssue] = []
    warnings: list[GateIssue] = []

    sections = _normalize_sections(data)
    full_text = _full_text(data, sections)
    title = str(data.get("title") or data.get("wechat_title") or "")

    _check_multi_signal_daily(data, sections, errors)
    _check_predictions_and_precision(data, sections, errors)
    _check_channel_inference(full_text, errors)
    _check_claim_evidence_contradiction(data, full_text, errors)
    _check_metric_dimension_mismatch(data, full_text, errors)
    _check_experiment_params(data, sections, full_text, errors)
    _check_source_lineage(sections, errors)
    _check_search_snippet_as_evidence(data, sections, errors)
    _check_headline(title, errors)
    _check_single_company_market_generalization(full_text, errors)
    _check_internal_copy_exposed(full_text, errors)
    _check_fabricated_data(data, errors)
    _check_future_publication(data, errors, now=now)
    _check_unsupported_fact(data, sections, full_text, errors)
    _check_unsupported_numeric_claim(sections, errors)
    _check_unsupported_sample(data, errors)
    _check_research_count_consistency(sections, warnings)

    status = "failed" if errors else "passed"
    return EditorialGateResult(status=status, errors=errors, warnings=warnings)


def is_bypass_allowed(report_or_mdx_data: dict, result: EditorialGateResult) -> bool:
    """Whether a signed-off ``editorial_exception`` may waive a failed gate.

    Requires ``editorial_exception`` to be a dict with a non-empty ``reason``
    and ``approved_at``, AND none of the failing error codes may be in
    :data:`NON_BYPASSABLE_ERROR_CODES`. A bare ``manual_reviewed``/
    ``manual_review`` flag — with no ``editorial_exception`` — never bypasses
    a hard failure.
    """
    if result.passed:
        return True
    data = report_or_mdx_data if isinstance(report_or_mdx_data, dict) else {}
    exception = data.get("editorial_exception")
    if not isinstance(exception, dict):
        return False
    if not str(exception.get("reason") or "").strip():
        return False
    if not str(exception.get("approved_at") or "").strip():
        return False
    if any(code in NON_BYPASSABLE_ERROR_CODES for code in result.error_codes):
        return False
    return True
