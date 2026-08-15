"""Repeatable founder growth scorecard from baseline + ledger.

baseline_snapshot is read-only historical reference.
current_experiment holds only the active period ledger counts/rates.
Never use baseline uniques as current funnel denominators.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from growth.ledger import (
    compute_funnel_rates,
    default_experiment_targets,
    default_ledger_template,
    derive_ledger_alerts,
    validate_ledger,
)


SCORECARD_SCHEMA_VERSION = 1


def _baseline_source_sum(baseline: dict[str, Any]) -> int:
    sources = baseline.get("wechat", {}).get("overlapping_source_readers", {})
    return int(sum(int(v) for v in sources.values()))


def _baseline_alerts(baseline: dict[str, Any]) -> list[dict[str, str]]:
    """Alerts derived only from read-only baseline aggregates."""
    alerts: list[dict[str, str]] = []
    wechat = baseline.get("wechat", {})
    unique = wechat.get("unique_readers_全部")
    source_sum = _baseline_source_sum(baseline)
    if unique is not None and source_sum != unique:
        alerts.append(
            {
                "code": "wechat_source_overlap",
                "severity": "warning",
                "message": (
                    f"基线参照：微信来源阅读人数合计 {source_sum} ≠ “全部”唯一阅读 {unique}；"
                    "来源可重叠，禁止相加当作唯一人数。"
                    "（此为 baseline_snapshot，不作当期漏斗分母）"
                ),
                "scope": "baseline_snapshot",
            }
        )
    alerts.append(
        {
            "code": "zhihu_missing_article_attribution",
            "severity": "warning",
            "message": (
                "基线参照：知乎仅为账号级日汇总，缺少文章级归因；"
                "不可对单篇内容下因果结论。"
            ),
            "scope": "baseline_snapshot",
        }
    )
    return alerts


def seed_ledger_from_baseline(
    baseline: dict[str, Any],
    *,
    start: str = "2026-08-13",
    end: str = "2026-08-26",
) -> dict[str, Any]:
    """Create a *current-period* ledger; do not copy baseline channel counts.

    Historical baseline stays read-only in scorecard.baseline_snapshot.
    channel_observed defaults to null; event counters default to 0.
    """
    ledger = default_ledger_template(start=start, end=end)

    targets = default_experiment_targets()
    for experiment in baseline.get("experiments_14d", []):
        for key, value in experiment.get("targets", {}).items():
            if key not in targets:
                continue
            targets[key] = (
                value
                if "行业" in value or "内部" in value or "实验" in value
                else f"{value}（内部实验目标，非行业基准）"
            )
    ledger["experiment_targets"] = targets

    ledger["alerts"] = derive_ledger_alerts(ledger)
    ledger["notes"] = (
        "Current experiment-period ledger only. "
        "Baseline aggregates are read-only under scorecard.baseline_snapshot "
        "and must not be used as current funnel denominators. "
        "channel_observed defaults to null; impressions/views default to null; "
        "website event counters default to 0 until the operator fills this period."
    )
    return validate_ledger(ledger)


def build_founder_scorecard(
    *,
    baseline: dict[str, Any],
    ledger: dict[str, Any] | None = None,
    generated_on: str | None = None,
) -> dict[str, Any]:
    """Assemble a repeatable founder scorecard with explicit period split."""
    active_ledger = (
        validate_ledger(ledger) if ledger is not None else seed_ledger_from_baseline(baseline)
    )
    funnel = compute_funnel_rates(active_ledger)
    current_alerts = list(active_ledger.get("alerts") or [])
    derived = derive_ledger_alerts(active_ledger)
    codes = {item["code"] for item in current_alerts}
    for item in derived:
        if item["code"] not in codes:
            current_alerts.append(item)
    for item in current_alerts:
        item.setdefault("scope", "current_experiment")

    wechat = baseline.get("wechat", {})
    zhihu = baseline.get("zhihu", {})
    unique = wechat.get("unique_readers_全部")
    source_sum = _baseline_source_sum(baseline)
    baseline_alerts = _baseline_alerts(baseline)

    # Merge alerts: baseline reference + current experiment (dedupe by code+scope).
    alerts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in baseline_alerts + current_alerts:
        key = (item["code"], item.get("scope", ""))
        if key in seen:
            continue
        seen.add(key)
        alerts.append(item)

    scorecard = {
        "schema_version": SCORECARD_SCHEMA_VERSION,
        "generated_on": generated_on or date.today().isoformat(),
        "privacy": {
            "raw_reports_copied": False,
            "user_pii_recorded": False,
            "contents": "aggregates_and_manual_counts_only",
        },
        "baseline_date": baseline.get("baseline_date"),
        "period": active_ledger["period"],
        "baseline_snapshot": {
            "role": "read_only_historical_reference",
            "baseline_date": baseline.get("baseline_date"),
            "wechat": {
                "unique_readers_全部": unique,
                "overlapping_source_readers_sum": source_sum,
                "sources_are_unique_people": False,
                "engagement": wechat.get("engagement", {}),
                "period": wechat.get("period"),
                "note": (
                    "历史基线只读参照。来源阅读人数可重叠，不可相加当作唯一人数。"
                    "禁止用作当期漏斗分母。"
                ),
            },
            "zhihu": {
                "totals": zhihu.get("totals", {}),
                "nonzero_read_days": zhihu.get("nonzero_read_days"),
                "peak": zhihu.get("peak", {}),
                "period": zhihu.get("period"),
                "article_level_attribution_available": False,
                "note": "账号级日汇总；缺文章级归因。只读参照，非当期实验计数。",
            },
        },
        "current_experiment": {
            "period": active_ledger["period"],
            "channel_observed": active_ledger["channel_observed"],
            "funnel_manual": active_ledger["funnel_manual"],
            "funnel_rates": funnel,
            "note": (
                "仅含当期实验台账。channel counts 默认 null；"
                "impressions/views 未录入时对应率为 n/a；"
                "不得把 baseline_snapshot 人数当成分母。"
            ),
        },
        # Convenience mirrors for operators reading markdown / older callers.
        "wechat": {
            "unique_readers_全部": unique,
            "overlapping_source_readers_sum": source_sum,
            "sources_are_unique_people": False,
            "engagement": wechat.get("engagement", {}),
            "note": "见 baseline_snapshot.wechat（只读参照，非当期分母）。",
            "scope": "baseline_snapshot",
        },
        "zhihu": {
            "totals": zhihu.get("totals", {}),
            "nonzero_read_days": zhihu.get("nonzero_read_days"),
            "peak": zhihu.get("peak", {}),
            "article_level_attribution_available": False,
            "note": "见 baseline_snapshot.zhihu（只读参照）。",
            "scope": "baseline_snapshot",
        },
        "funnel_manual_slots": active_ledger["funnel_manual"],
        "funnel_rates": funnel,
        "experiment_targets": active_ledger["experiment_targets"],
        "target_kind": "internal_experiment_goals_not_industry_benchmarks",
        "alerts": alerts,
        "limitations": [
            "样本小，禁止从小样本推因果。",
            "微信重叠来源不可当唯一人数。",
            "知乎缺文章级归因。",
            "禁止跨周期漏斗：基线人数不可作当期分母。",
            "当期 impressions/views 未录入或分母为 0 时转化率为 n/a。",
            "漏斗事件字段对齐网站 tool_view / subscribe_click / "
            "subscribe_success，以及公众号关键词「复盘表」回复数。",
            "目标为可匿名观测的内部实验目标，不是行业基准；无访谈线索目标。",
        ],
    }
    return scorecard


def render_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    baseline = scorecard["baseline_snapshot"]
    current = scorecard["current_experiment"]
    funnel = current["funnel_rates"]
    lines = [
        f"# Founder Growth Scorecard（{scorecard['period']['label']}）",
        "",
        f"> 生成日期：{scorecard['generated_on']}。"
        "仅聚合指标与手工漏斗计数；未复制原始报表，未记录用户 PII。"
        "目标为内部实验目标，非行业基准。"
        "**baseline_snapshot 只读参照；current_experiment 为当期台账；禁止跨周期漏斗。**",
        "",
        "## baseline_snapshot（只读历史参照）",
        "",
        f"- 基线日期：{baseline.get('baseline_date')}",
        f"- 角色：`{baseline.get('role')}`",
        "",
        "### 微信（基线）",
        "",
        f"- “全部”唯一阅读人数：**{baseline['wechat']['unique_readers_全部']}**",
        f"- 来源阅读人数合计（可重叠）：**{baseline['wechat']['overlapping_source_readers_sum']}**",
        f"- 来源可否当作唯一人数：**否**（`sources_are_unique_people=false`）",
        f"- 分享人数：{baseline['wechat']['engagement'].get('share_people')}",
        f"- 阅读原文人数：{baseline['wechat']['engagement'].get('original_link_people')}",
        f"- 说明：{baseline['wechat']['note']}",
        "",
        "### 知乎（基线）",
        "",
        f"- 阅读合计：{baseline['zhihu']['totals'].get('reads')}",
        (
            "- 互动合计（赞+藏+分享）："
            f"{int(baseline['zhihu']['totals'].get('likes', 0) or 0)}"
            f"+{int(baseline['zhihu']['totals'].get('favorites', 0) or 0)}"
            f"+{int(baseline['zhihu']['totals'].get('shares', 0) or 0)}"
        ),
        f"- 非零阅读日：{baseline['zhihu']['nonzero_read_days']}",
        "- 文章级归因可用：**否**",
        f"- 说明：{baseline['zhihu']['note']}",
        "",
        "## current_experiment（当期实验）",
        "",
        f"- 周期：{current['period']['start']} ~ {current['period']['end']}",
        f"- 说明：{current['note']}",
        "",
        "### 当期渠道计数（默认 null，待录入）",
        "",
    ]
    for key, value in current["channel_observed"].items():
        display = "null" if value is None else value
        lines.append(f"- `{key}`: {display}")

    lines.extend(
        [
            "",
            "### 当期漏斗计数（可匿名观测）",
            "",
            "- 字段：`impressions` / `views`（未录入默认 null）+"
            "`tool_views`（网站 `tool_view`）/ `keyword_replies`（「复盘表」）/ "
            "`subscribe_click` / `subscribe_success`。"
            "无访谈/一对一线索计数。",
            "",
        ]
    )
    for key, value in current["funnel_manual"].items():
        display = "null" if value is None else value
        lines.append(f"- `{key}`: {display}")

    lines.extend(["", "### 当期漏斗转化率（零/缺失分母 → n/a）", ""])
    for key, display in funnel["rates_display"].items():
        lines.append(f"- `{key}`: {display}")

    lines.extend(["", "## 内部实验目标（非行业基准）", ""])
    for key, value in scorecard["experiment_targets"].items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## 告警", ""])
    if scorecard["alerts"]:
        for alert in scorecard["alerts"]:
            scope = alert.get("scope", "")
            scope_bit = f" scope={scope}" if scope else ""
            lines.append(
                f"- [{alert['severity']}] `{alert['code']}`{scope_bit}: {alert['message']}"
            )
    else:
        lines.append("- （无）")

    lines.extend(["", "## 局限", ""])
    for item in scorecard["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_scorecard_artifacts(
    scorecard: dict[str, Any],
    *,
    json_path: Path | str,
    markdown_path: Path | str,
) -> None:
    json_file = Path(json_path)
    md_file = Path(markdown_path)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(
        json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_file.write_text(render_scorecard_markdown(scorecard), encoding="utf-8")
