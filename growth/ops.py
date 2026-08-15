"""Weekly decision pack: funnel + scorecard + combat context."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from growth.combat_pack import build_combat_pack, render_combat_pack_markdown
from growth.ledger import compute_funnel_rates, derive_ledger_alerts, validate_ledger
from growth.outreach import build_outreach_pack, render_outreach_markdown
from growth.scorecard import (
    build_founder_scorecard,
    render_scorecard_markdown,
    seed_ledger_from_baseline,
)


def build_weekly_decisions(
    *,
    scorecard: dict[str, Any],
    combat_pack: dict[str, Any],
    funnel: dict[str, Any],
) -> dict[str, Any]:
    """Produce operator decisions without claiming causality."""
    alerts = scorecard.get("alerts", [])
    alert_codes = {item["code"] for item in alerts}
    zero_slots = funnel.get("zero_denominator_slots", [])

    decisions = [
        {
            "id": "use_unique_readers_only",
            "priority": 1,
            "decision": "周复盘只采用微信“全部”唯一阅读人数，不将来源渠道相加。",
            "because": (
                "来源归因可重叠；"
                "baseline_snapshot.wechat.sources_are_unique_people=false。"
            ),
        },
        {
            "id": "zhihu_trend_only",
            "priority": 1,
            "decision": "知乎只观察账号级趋势与非零阅读日，不对单篇下因果结论。",
            "because": "zhihu_missing_article_attribution 告警生效中。"
            if "zhihu_missing_article_attribution" in alert_codes
            else "知乎默认无文章级归因。",
        },
        {
            "id": "prefer_tool_checklist_content",
            "priority": 2,
            "decision": "本周内容优先五指标复盘 / 缺货排查 / 运营决策清单，不主推泛日报搬运。",
            "because": "作战包主题与内部实验目标对齐；小样本仅作实验假设。",
        },
        {
            "id": "fill_manual_funnel",
            "priority": 2,
            "decision": (
                "只录入可匿名观测台账：内容按期准备率、关键词「复盘表」回复数、"
                "工具页访问、公开平台收藏/赞同/阅读变化；"
                "以及 impressions/views 与 subscribe_click/subscribe_success；"
                "零或缺失分母转化率记为 n/a；禁止把基线人数当当期分母；不记录访谈线索。"
            ),
            "because": (
                f"当前 n/a 槽位: {', '.join(zero_slots) if zero_slots else '无'}。"
            ),
        },
        {
            "id": "self_serve_funnel_only",
            "priority": 3,
            "decision": (
                "转化只走公开内容 → 关注公众号 → 回复「复盘表」→ 自助周复盘工具；"
                "可公开订阅；禁止一对一联系、加微信、访谈或索取公司/点位身份。"
            ),
            "because": "创始人仍在智能柜公司任职，不适合开展运营商访谈。",
        },
        {
            "id": "no_auto_publish",
            "priority": 1,
            "decision": "所有微信/知乎内容人工审核后发布；命令只生成计划与台账，不触发发布。",
            "because": "combat_pack 全部 auto_publish=false。",
        },
        {
            "id": "use_piece_cta_url",
            "priority": 2,
            "decision": (
                "发布时粘贴该条可复制 CTA URL（工具页 + 本条 UTM）；"
                "文案唯一行动为回复「复盘表」或打开自助工具。"
            ),
            "because": "combat_pack 每条含 cta_url，禁止再用访谈 CTA。",
        },
    ]

    return {
        "schema_version": 1,
        "generated_on": scorecard.get("generated_on"),
        "period": scorecard.get("period"),
        "hours_budget_per_week": combat_pack.get("hours_budget_per_week"),
        "estimated_hours_per_week": combat_pack.get("estimated_hours_per_week"),
        "decisions": decisions,
        "alerts": alerts,
        "funnel_rates_display": funnel.get("rates_display", {}),
        "disclaimer": (
            "本决策清单用于单人创始人周运营，不构成因果证明，"
            "目标为内部实验目标而非行业基准。"
        ),
    }


def render_weekly_decisions_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 周决策清单（{payload['period']['label']}）",
        "",
        f"> {payload['disclaimer']}",
        "",
        f"- 生成日期：{payload['generated_on']}",
        f"- 预估工时/周：{payload['estimated_hours_per_week']}h"
        f"（预算 {payload['hours_budget_per_week']['min']}–"
        f"{payload['hours_budget_per_week']['max']}h）",
        "",
        "## 决策",
        "",
    ]
    for item in sorted(payload["decisions"], key=lambda row: row["priority"]):
        lines.append(f"### P{item['priority']} · {item['id']}")
        lines.append("")
        lines.append(f"- 决策：{item['decision']}")
        lines.append(f"- 依据：{item['because']}")
        lines.append("")

    lines.extend(["## 漏斗转化率", ""])
    for key, value in payload["funnel_rates_display"].items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## 告警", ""])
    if payload["alerts"]:
        for alert in payload["alerts"]:
            lines.append(f"- [{alert['severity']}] `{alert['code']}`: {alert['message']}")
    else:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)


def generate_founder_growth_ops(
    *,
    baseline: dict[str, Any],
    ledger: dict[str, Any] | None = None,
    start_date: str = "2026-08-13",
    generated_on: str | None = None,
    slots_per_week: int = 4,
) -> dict[str, Any]:
    """One-shot assemble scorecard, funnel, combat pack, outreach, decisions."""
    active_ledger = (
        validate_ledger(ledger)
        if ledger is not None
        else seed_ledger_from_baseline(baseline, start=start_date)
    )
    # Ensure alerts are present even if caller passed a sparse ledger.
    if not active_ledger.get("alerts"):
        active_ledger = dict(active_ledger)
        active_ledger["alerts"] = derive_ledger_alerts(active_ledger)

    scorecard = build_founder_scorecard(
        baseline=baseline,
        ledger=active_ledger,
        generated_on=generated_on or date.today().isoformat(),
    )
    funnel = compute_funnel_rates(active_ledger)
    combat = build_combat_pack(start_date=start_date)
    outreach = build_outreach_pack(slots_per_week=slots_per_week)
    decisions = build_weekly_decisions(
        scorecard=scorecard,
        combat_pack=combat,
        funnel=funnel,
    )

    return {
        "schema_version": 1,
        "generated_on": scorecard["generated_on"],
        "privacy": scorecard["privacy"],
        "ledger": active_ledger,
        "scorecard": scorecard,
        "funnel": funnel,
        "combat_pack": combat,
        "outreach": outreach,
        "weekly_decisions": decisions,
    }


def write_founder_growth_ops_artifacts(
    bundle: dict[str, Any],
    *,
    out_dir: Path | str,
) -> dict[str, Path]:
    """Write JSON/Markdown artifacts for operator use."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    data_dir = root / "data"
    docs_dir = root / "docs"
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "ledger": data_dir / "experiment-ledger.json",
        "scorecard_json": data_dir / "founder-scorecard.json",
        "funnel_json": data_dir / "funnel-rates.json",
        "combat_json": data_dir / "combat-pack.json",
        "outreach_json": data_dir / "outreach-pack.json",
        "decisions_json": data_dir / "weekly-decisions.json",
        "scorecard_md": docs_dir / "founder-scorecard.md",
        "combat_md": docs_dir / "combat-pack.md",
        "outreach_md": docs_dir / "outreach-templates.md",
        "decisions_md": docs_dir / "weekly-decisions.md",
    }

    paths["ledger"].write_text(
        json.dumps(bundle["ledger"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["scorecard_json"].write_text(
        json.dumps(bundle["scorecard"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["funnel_json"].write_text(
        json.dumps(bundle["funnel"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["combat_json"].write_text(
        json.dumps(bundle["combat_pack"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["outreach_json"].write_text(
        json.dumps(bundle["outreach"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["decisions_json"].write_text(
        json.dumps(bundle["weekly_decisions"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["scorecard_md"].write_text(
        render_scorecard_markdown(bundle["scorecard"]), encoding="utf-8"
    )
    paths["combat_md"].write_text(
        render_combat_pack_markdown(bundle["combat_pack"]), encoding="utf-8"
    )
    paths["outreach_md"].write_text(
        render_outreach_markdown(bundle["outreach"]), encoding="utf-8"
    )
    paths["decisions_md"].write_text(
        render_weekly_decisions_markdown(bundle["weekly_decisions"]), encoding="utf-8"
    )
    return paths
