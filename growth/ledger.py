"""Experiment ledger schema validation and funnel aggregation.

Current-period only: never use historical baseline counts as experiment
denominators. Website / OA event names map as:
  tool_view → tool_views (count)
  keyword「复盘表」replies → keyword_replies
  subscribe_click / subscribe_success → same field names

Interview / one-to-one outreach counters are intentionally absent.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from growth.rates import format_rate, safe_rate

SCHEMA_VERSION = 1

# Counts of website events / acquisition; impressions & views may be unset (null).
FUNNEL_NULLABLE_KEYS = ("impressions", "views")
FUNNEL_COUNTER_KEYS = (
    "tool_views",  # website event: tool_view
    "keyword_replies",  # OA exact-match「复盘表」
    "subscribe_click",
    "subscribe_success",
)
FUNNEL_SLOT_KEYS = FUNNEL_NULLABLE_KEYS + FUNNEL_COUNTER_KEYS

FUNNEL_RATE_KEYS = (
    "impression_to_view",
    "view_to_tool",
    "tool_to_subscribe_click",
    "subscribe_click_to_success",
)

LEDGER_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://zerorealm.local/schemas/founder-experiment-ledger.json",
    "title": "FounderExperimentLedger",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "period",
        "privacy",
        "funnel_manual",
        "channel_observed",
        "experiment_targets",
        "alerts",
        "notes",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": SCHEMA_VERSION},
        "period": {
            "type": "object",
            "additionalProperties": False,
            "required": ["start", "end", "label"],
            "properties": {
                "start": {"type": "string", "minLength": 10},
                "end": {"type": "string", "minLength": 10},
                "label": {"type": "string", "minLength": 1},
            },
        },
        "privacy": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "raw_reports_copied",
                "user_pii_recorded",
                "contents",
            ],
            "properties": {
                "raw_reports_copied": {"type": "boolean", "const": False},
                "user_pii_recorded": {"type": "boolean", "const": False},
                "contents": {"type": "string", "const": "aggregates_and_manual_counts_only"},
            },
        },
        "funnel_manual": {
            "type": "object",
            "additionalProperties": False,
            "required": list(FUNNEL_SLOT_KEYS),
            "properties": {
                **{
                    key: {"type": ["integer", "null"], "minimum": 0}
                    for key in FUNNEL_NULLABLE_KEYS
                },
                **{key: {"type": "integer", "minimum": 0} for key in FUNNEL_COUNTER_KEYS},
            },
            "description": (
                "Current-period anonymous-observable counts. "
                "impressions/views default null until entered; "
                "tool_views counts website tool_view events; "
                "keyword_replies counts OA「复盘表」exact matches."
            ),
        },
        "channel_observed": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "wechat_unique_readers",
                "wechat_overlapping_source_readers_sum",
                "wechat_share_people",
                "wechat_original_link_people",
                "zhihu_reads",
                "zhihu_engagement",
                "zhihu_article_level_attribution_available",
            ],
            "properties": {
                "wechat_unique_readers": {"type": ["integer", "null"], "minimum": 0},
                "wechat_overlapping_source_readers_sum": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                },
                "wechat_share_people": {"type": ["integer", "null"], "minimum": 0},
                "wechat_original_link_people": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                },
                "zhihu_reads": {"type": ["integer", "null"], "minimum": 0},
                "zhihu_engagement": {"type": ["integer", "null"], "minimum": 0},
                "zhihu_article_level_attribution_available": {"type": "boolean"},
            },
            "description": (
                "Current experiment-period channel counts only. "
                "Default null; never seed from historical baseline."
            ),
        },
        "experiment_targets": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "required": [
                "content_prep_on_time_rate",
                "keyword_replies",
                "tool_views",
                "public_platform_engagement_delta",
            ],
            "properties": {
                "content_prep_on_time_rate": {"type": "string", "minLength": 1},
                "keyword_replies": {"type": "string", "minLength": 1},
                "tool_views": {"type": "string", "minLength": 1},
                "public_platform_engagement_delta": {"type": "string", "minLength": 1},
            },
            "description": "Anonymous-observable internal experiment goals; not industry benchmarks.",
        },
        "alerts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "severity", "message"],
                "properties": {
                    "code": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "critical"],
                    },
                    "message": {"type": "string"},
                },
            },
        },
        "notes": {"type": "string"},
    },
}


class LedgerError(ValueError):
    """Raised when a ledger fails schema or integrity checks."""


def default_funnel_manual() -> dict[str, Any]:
    return {
        **{key: None for key in FUNNEL_NULLABLE_KEYS},
        **{key: 0 for key in FUNNEL_COUNTER_KEYS},
    }


def default_experiment_targets() -> dict[str, str]:
    return {
        "content_prep_on_time_rate": (
            "计划内容按期准备率（草稿/配置就绪人工核对；未观测不填造）"
        ),
        "keyword_replies": "关键词「复盘表」回复数（公众号后台人工计数；未观测保持 0）",
        "tool_views": "工具页访问（网站 tool_view / 人工录入；未观测保持 0）",
        "public_platform_engagement_delta": (
            "公开平台收藏/赞同/阅读变化（仅渠道报表新鲜时录入，否则保持 null，不虚构）"
        ),
    }


def default_ledger_template(
    *,
    start: str = "2026-08-13",
    end: str = "2026-08-26",
    label: str = "founder_14d_2026-08-13",
) -> dict[str, Any]:
    """Empty current-period ledger; channel counts null, event counters 0."""
    return {
        "schema_version": SCHEMA_VERSION,
        "period": {"start": start, "end": end, "label": label},
        "privacy": {
            "raw_reports_copied": False,
            "user_pii_recorded": False,
            "contents": "aggregates_and_manual_counts_only",
        },
        "funnel_manual": default_funnel_manual(),
        "channel_observed": {
            "wechat_unique_readers": None,
            "wechat_overlapping_source_readers_sum": None,
            "wechat_share_people": None,
            "wechat_original_link_people": None,
            "zhihu_reads": None,
            "zhihu_engagement": None,
            "zhihu_article_level_attribution_available": False,
        },
        "experiment_targets": default_experiment_targets(),
        "alerts": [],
        "notes": "",
    }


def validate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate ledger against embedded schema; return a deep copy."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency is required in CI
        raise LedgerError("jsonschema is required to validate ledgers") from exc

    try:
        jsonschema.Draft202012Validator(LEDGER_SCHEMA).validate(ledger)
    except jsonschema.ValidationError as exc:
        raise LedgerError(f"ledger schema validation failed: {exc.message}") from exc
    return deepcopy(ledger)


def load_ledger(path: Path | str) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.is_file():
        raise LedgerError(f"ledger not found: {report_path}")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"ledger is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LedgerError("ledger root must be an object")
    return validate_ledger(payload)


def write_ledger_template(path: Path | str, *, template: dict[str, Any] | None = None) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = validate_ledger(template or default_ledger_template())
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_ledger_schema(path: Path | str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(LEDGER_SCHEMA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compute_funnel_rates(ledger: dict[str, Any]) -> dict[str, Any]:
    """Derive current-period funnel rates; None means zero or missing denominator.

    Never mixes historical baseline channel uniques into these rates.
    """
    validated = validate_ledger(ledger)
    funnel = validated["funnel_manual"]

    impressions = funnel["impressions"]
    views = funnel["views"]
    tool_views = funnel["tool_views"]
    subscribe_click = funnel["subscribe_click"]
    subscribe_success = funnel["subscribe_success"]

    rates = {
        "impression_to_view": safe_rate(views, impressions),
        "view_to_tool": safe_rate(tool_views, views),
        "tool_to_subscribe_click": safe_rate(subscribe_click, tool_views),
        "subscribe_click_to_success": safe_rate(subscribe_success, subscribe_click),
    }
    return {
        "counts": {key: funnel[key] for key in FUNNEL_SLOT_KEYS},
        "rates": rates,
        "rates_display": {key: format_rate(value) for key, value in rates.items()},
        "zero_denominator_slots": [key for key, value in rates.items() if value is None],
        "website_event_map": {
            "tool_views": "tool_view",
            "keyword_replies": "oa_keyword_fupanbiao",
            "subscribe_click": "subscribe_click",
            "subscribe_success": "subscribe_success",
        },
    }


def derive_ledger_alerts(ledger: dict[str, Any]) -> list[dict[str, str]]:
    """Build overlap + Zhihu attribution alerts from *current* observed fields."""
    validated = validate_ledger(ledger)
    observed = validated["channel_observed"]
    alerts: list[dict[str, str]] = []

    unique = observed["wechat_unique_readers"]
    source_sum = observed["wechat_overlapping_source_readers_sum"]
    if unique is not None and source_sum is not None and source_sum != unique:
        alerts.append(
            {
                "code": "wechat_source_overlap",
                "severity": "warning",
                "message": (
                    f"微信来源阅读人数合计 {source_sum} ≠ “全部”唯一阅读 {unique}；"
                    "来源可重叠，禁止相加当作唯一人数。"
                ),
            }
        )

    if not observed["zhihu_article_level_attribution_available"]:
        alerts.append(
            {
                "code": "zhihu_missing_article_attribution",
                "severity": "warning",
                "message": (
                    "知乎仅为账号级日汇总，缺少文章级归因；"
                    "不可对单篇内容下因果结论。"
                ),
            }
        )

    return alerts
