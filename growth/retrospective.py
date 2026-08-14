"""Evidence-based operating retrospective: collection vs channel business metrics."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from growth.freshness import classify_freshness
from growth.scorecard import build_founder_scorecard, seed_ledger_from_baseline
from growth.wechat import WechatTendencySummary
from growth.zhihu import ZhihuDailySummary

RETROSPECTIVE_SCHEMA_VERSION = 1
FOUNDER_OWNER = "founder"
FOUNDER_GITHUB = "LoganWang123"
TOOL_PAGE_PATH = "/tools/smart-cabinet-weekly-review"
WEBSITE_EVENTS = ("tool_view", "subscribe_click", "interview_click")


def _aggregates_match_baseline(
    *,
    wechat: WechatTendencySummary,
    zhihu: ZhihuDailySummary,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    base_wechat = baseline.get("wechat", {})
    base_zhihu = baseline.get("zhihu", {})
    wechat_match = (
        wechat.period_start == base_wechat.get("period", {}).get("start")
        and wechat.period_end == base_wechat.get("period", {}).get("end")
        and wechat.unique_readers == base_wechat.get("unique_readers_全部")
    )
    zhihu_match = (
        zhihu.period_start == base_zhihu.get("period", {}).get("start")
        and zhihu.period_end == base_zhihu.get("period", {}).get("end")
        and zhihu.total_reads == (base_zhihu.get("totals") or {}).get("reads")
    )
    return {
        "wechat_aggregates_match_baseline": wechat_match,
        "zhihu_aggregates_match_baseline": zhihu_match,
        "new_outcome_window": not (wechat_match and zhihu_match),
    }


def select_next_work_item(
    *,
    review_date: str,
    collection_ok: bool,
    wechat_freshness: dict[str, Any],
    experiment_end: str,
) -> dict[str, Any]:
    next_review = (
        datetime.strptime(review_date, "%Y-%m-%d").date() + timedelta(days=7)
    ).isoformat()
    if not collection_ok:
        return {
            "id": "repair_daily_collection",
            "owner": FOUNDER_OWNER,
            "owner_github": FOUNDER_GITHUB,
            "title": "修复 Daily Collection，恢复 crawl/rule-clean/dedupe/digest",
            "seven_day_metric": {
                "name": "scheduled_collection_success",
                "definition": "下一轮 cron Daily Collection conclusion=success 且 sources_success>=1",
            },
            "continue_threshold": "定时采集成功且健康门通过",
            "stop_threshold": "连续两次定时采集失败则停止扩大源范围，先修健康门/超时源",
            "next_review_date": next_review,
            "rationale": "技术采集失败时不应把渠道阅读当作成长结果。",
        }

    if wechat_freshness.get("status") != "current" or not wechat_freshness.get(
        "covers_experiment_start"
    ):
        return {
            "id": "import_fresh_channel_reports_7d",
            "owner": FOUNDER_OWNER,
            "owner_github": FOUNDER_GITHUB,
            "title": "导入覆盖当期实验窗口的微信/知乎新报表，经 freshness 闸门后再填 current_experiment",
            "seven_day_metric": {
                "name": "fresh_wechat_report_covers_current_experiment",
                "definition": (
                    "新微信 tendency 的 period.end 距复盘日 ≤1 天，"
                    "且 covers_experiment_start=true，"
                    "且 current_experiment.channel_observed.wechat_unique_readers 非 null"
                ),
            },
            "continue_threshold": (
                "导入覆盖 2026-08-13 之后的微信“全部”唯一阅读；"
                "禁止把基线 unique_readers 当当期分母"
            ),
            "stop_threshold": (
                f"到 {next_review} 仍只有 period.end≤"
                f"{wechat_freshness.get('period_end')} 的微信报表"
                "→ 停止把 14 天实验当作可量化增长结论；工具/清单文可继续人工发布，但不声称阅读提升"
            ),
            "next_review_date": next_review,
            "rationale": (
                "渠道结果数据已过期；采集健康不能替代微信/知乎业务结果。"
                f" 实验窗口至 {experiment_end}。"
            ),
        }

    return {
        "id": "fill_current_funnel_and_evaluate",
        "owner": FOUNDER_OWNER,
        "owner_github": FOUNDER_GITHUB,
        "title": "填入当期漏斗与渠道计数，对照内部实验目标复盘",
        "seven_day_metric": {
            "name": "current_experiment_wechat_unique_readers_present",
            "definition": "current_experiment.channel_observed.wechat_unique_readers 为非负整数",
        },
        "continue_threshold": "当期唯一阅读已录入且漏斗至少有一个非 n/a 转化率",
        "stop_threshold": "仍无手工漏斗/网站事件计数则不评估 14 天目标达成",
        "next_review_date": next_review,
        "rationale": "报表已覆盖当期，下一步是填台账而不是用基线人数做漏斗。",
    }


def _channel_import_decision(wechat_freshness: dict[str, Any], zhihu_freshness: dict[str, Any]) -> dict[str, Any]:
    wechat_ok = bool(wechat_freshness.get("can_fill_current_experiment"))
    applied = wechat_ok  # WeChat unique readers are the primary current-period fill
    if applied:
        reason = "wechat report is current and covers experiment start"
    else:
        reason = (
            f"wechat period_end {wechat_freshness.get('period_end')} "
            f"status={wechat_freshness.get('status')}; "
            "refusing to copy baseline unique readers into current_experiment"
        )
    return {
        "attempted": True,
        "applied": applied,
        "zhihu_can_fill": bool(zhihu_freshness.get("can_fill_current_experiment")),
        "reason": reason,
    }


def build_ops_retrospective(
    *,
    review_date: str,
    baseline: dict[str, Any],
    wechat: WechatTendencySummary,
    zhihu: ZhihuDailySummary,
    wechat_filename: str,
    zhihu_filename: str,
    zhihu_aliases: list[str] | tuple[str, ...] = (),
    wechat_selection_reason: str = "",
    zhihu_selection_reason: str = "",
    collection: dict[str, Any] | None = None,
    experiment_start: str = "2026-08-13",
    experiment_end: str = "2026-08-26",
    generated_on: str | None = None,
    website: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated = generated_on or date.today().isoformat()
    wechat_freshness = classify_freshness(
        period_end=wechat.period_end,
        review_date=review_date,
        experiment_start=experiment_start,
    )
    zhihu_freshness = classify_freshness(
        period_end=zhihu.period_end,
        review_date=review_date,
        experiment_start=experiment_start,
    )
    match = _aggregates_match_baseline(wechat=wechat, zhihu=zhihu, baseline=baseline)
    ledger = seed_ledger_from_baseline(
        baseline, start=experiment_start, end=experiment_end
    )
    scorecard = build_founder_scorecard(
        baseline=baseline, ledger=ledger, generated_on=generated
    )
    current = scorecard["current_experiment"]["channel_observed"]
    import_decision = _channel_import_decision(wechat_freshness, zhihu_freshness)
    collection = dict(collection or {})
    collection_ok = collection.get("conclusion") == "success" and int(
        (collection.get("metrics") or {}).get("sources_success") or 0
    ) >= 1
    next_item = select_next_work_item(
        review_date=review_date,
        collection_ok=collection_ok if collection else True,
        wechat_freshness=wechat_freshness,
        experiment_end=experiment_end,
    )
    if not collection:
        collection_ok = True

    website_payload = website or {
        "inspected": True,
        "repo": "zerorealm-website",
        "tool_path": TOOL_PAGE_PATH,
        "events_wired": list(WEBSITE_EVENTS),
        "local_event_counts_available": False,
        "note": (
            "官网工具页已埋点 tool_view / subscribe_click / interview_click（PostHog）；"
            "本仓库无 PostHog 导出。漏斗保持手工计数，不虚构。"
        ),
    }

    return {
        "schema_version": RETROSPECTIVE_SCHEMA_VERSION,
        "review_date": review_date,
        "generated_on": generated,
        "privacy": {
            "raw_reports_copied": False,
            "user_pii_recorded": False,
            "contents": "aggregates_and_run_metadata_only",
        },
        "separation": {
            "technical_collection": "GitHub Actions Daily Collection health only",
            "business_channels": "WeChat unique readers + Zhihu account-day totals only",
        },
        "technical_collection": {
            **collection,
            "kind": "technical_collection",
            "not_business_metrics": True,
            "health_ok": collection_ok if collection else None,
        },
        "business_channels": {
            "wechat": {
                "filename": wechat_filename,
                "selection_reason": wechat_selection_reason,
                "period": {"start": wechat.period_start, "end": wechat.period_end},
                "unique_readers_全部": wechat.unique_readers,
                "overlapping_source_readers": dict(wechat.overlapping_source_readers),
                "engagement": {
                    "share_people": wechat.share_people,
                    "original_link_people": wechat.original_link_people,
                    "published_articles": wechat.published_articles,
                },
                "freshness": wechat_freshness,
                "note": "“全部”为唯一阅读人数；来源可重叠，禁止相加。",
            },
            "zhihu": {
                "filename": zhihu_filename,
                "aliases_not_selected": list(zhihu_aliases),
                "selection_reason": zhihu_selection_reason,
                "period": {"start": zhihu.period_start, "end": zhihu.period_end},
                "totals": {
                    "reads": zhihu.total_reads,
                    "likes": zhihu.total_likes,
                    "favorites": zhihu.total_favorites,
                    "shares": zhihu.total_shares,
                    "comments": zhihu.total_comments,
                },
                "nonzero_read_days": zhihu.nonzero_read_days,
                "peak": {"date": zhihu.peak_date, "reads": zhihu.peak_reads},
                "freshness": zhihu_freshness,
                "article_level_attribution_available": False,
                "note": "账号级日汇总；缺文章级归因。",
            },
            "baseline_comparison": match,
            "current_experiment_import": import_decision,
            "current_experiment_channel_observed": current,
        },
        "website": website_payload,
        "funnel_manual": scorecard["current_experiment"]["funnel_manual"],
        "funnel_rates_display": scorecard["current_experiment"]["funnel_rates"]["rates_display"],
        "next_work_item": next_item,
        "limitations": [
            "未复制原始报表，未记录用户 PII。",
            "技术采集指标与微信/知乎业务指标分列，禁止混用。",
            "报表过期时不把 baseline unique readers 写入 current_experiment。",
            "官网漏斗无本地事件导出时保持 0 / n/a，不虚构转化。",
            "小样本禁止因果结论；目标为内部实验目标。",
        ],
        "fabricated_outcomes": False,
    }


def render_ops_retrospective_markdown(payload: dict[str, Any]) -> str:
    tech = payload["technical_collection"]
    business = payload["business_channels"]
    wechat = business["wechat"]
    zhihu = business["zhihu"]
    nxt = payload["next_work_item"]
    metrics = tech.get("metrics") or {}
    lines = [
        f"# 运营复盘（{payload['review_date']}）",
        "",
        "> 技术采集指标与微信/知乎业务指标分列。"
        "未复制原始报表，未记录用户 PII。不过期数据不编造成果。",
        "",
        f"- 生成日期：{payload['generated_on']}",
        f"- 原始报表入库：**否**（`raw_reports_copied={payload['privacy']['raw_reports_copied']}`）",
        f"- 虚构成果：**否**（`fabricated_outcomes={payload['fabricated_outcomes']}`）",
        "",
        "## A. 技术采集（GitHub Actions Daily Collection）",
        "",
        f"- 性质：{tech.get('kind')}；**不是**微信/知乎经营结果",
        f"- run：`{tech.get('run_id')}` {tech.get('html_url') or ''}".rstrip(),
        f"- event：`{tech.get('event')}`  conclusion：**{tech.get('conclusion')}**",
        f"- 采集日期：{tech.get('collection_date')}",
        f"- head_sha：`{tech.get('head_sha')}`",
        f"- 工作流耗时：{tech.get('duration_seconds_workflow')}s；"
        f"crawl `{metrics.get('duration_seconds', tech.get('duration_seconds_crawl'))}`s",
        f"- sources_total：{metrics.get('sources_total')}",
        f"- sources_success：{metrics.get('sources_success')}",
        f"- sources_failed：{metrics.get('sources_failed')}",
        f"- items_new：{metrics.get('items_new')}；items_total：{metrics.get('items_total')}；"
        f"items_duplicate：{metrics.get('items_duplicate')}",
        f"- artifact：{ (tech.get('artifact') or {}).get('name') } "
        f"id={(tech.get('artifact') or {}).get('id')} "
        f"bytes={(tech.get('artifact') or {}).get('size_bytes')}",
        f"- 失败源：{', '.join(metrics.get('errors') or []) or '（无）'}",
        "",
        "## B. 微信 / 知乎业务指标（只读聚合）",
        "",
        "### 数据新鲜度",
        "",
        (
            f"- 微信报表 `{wechat['filename']}` 周期 {wechat['period']['start']}~"
            f"{wechat['period']['end']}；lag_days={wechat['freshness']['lag_days']}；"
            f"status=**{wechat['freshness']['status']}**；"
            f"covers_experiment_start={wechat['freshness']['covers_experiment_start']}"
        ),
        (
            f"- 知乎报表 `{zhihu['filename']}` 周期 {zhihu['period']['start']}~"
            f"{zhihu['period']['end']}；lag_days={zhihu['freshness']['lag_days']}；"
            f"status=**{zhihu['freshness']['status']}**"
        ),
        (
            f"- 与基线聚合是否一致：微信 "
            f"{business['baseline_comparison']['wechat_aggregates_match_baseline']}，"
            f"知乎 {business['baseline_comparison']['zhihu_aggregates_match_baseline']}；"
            f"new_outcome_window="
            f"{business['baseline_comparison']['new_outcome_window']}"
        ),
        (
            f"- current_experiment 导入：applied="
            f"**{business['current_experiment_import']['applied']}**；"
            f"{business['current_experiment_import']['reason']}"
        ),
        "",
        "### 微信（“全部”=唯一阅读）",
        "",
        f"- 全部唯一阅读人数：**{wechat['unique_readers_全部']}**",
        f"- 搜一搜（可重叠）：{wechat['overlapping_source_readers'].get('搜一搜')}",
        f"- 推荐（可重叠）：{wechat['overlapping_source_readers'].get('推荐')}",
        f"- 分享人数：{wechat['engagement']['share_people']}；"
        f"阅读原文：{wechat['engagement']['original_link_people']}；"
        f"发表篇数：{wechat['engagement']['published_articles']}",
        f"- {wechat['note']}",
        "",
        "### 知乎（账号级日汇总）",
        "",
        f"- 阅读合计：**{zhihu['totals']['reads']}**",
        f"- 赞/藏/分享：{zhihu['totals']['likes']}/{zhihu['totals']['favorites']}/{zhihu['totals']['shares']}",
        f"- 非零阅读日：{zhihu['nonzero_read_days']}；峰值 {zhihu['peak']['date']}={zhihu['peak']['reads']}",
        f"- 未选用的等价文件：{', '.join(zhihu.get('aliases_not_selected') or []) or '（无）'}",
        f"- {zhihu['note']}",
        "",
        "### 当期实验台账（禁止用基线当分子分母）",
        "",
    ]
    for key, value in business["current_experiment_channel_observed"].items():
        lines.append(f"- `{key}`: {'null' if value is None else value}")
    lines.extend(["", "### 官网漏斗（无本地导出则不虚构）", ""])
    website = payload.get("website") or {}
    lines.append(f"- {website.get('note', '')}")
    for key, value in payload["funnel_manual"].items():
        lines.append(f"- `{key}`: {'null' if value is None else value}")
    lines.extend(["", "### 漏斗转化率", ""])
    for key, value in payload["funnel_rates_display"].items():
        lines.append(f"- `{key}`: {value}")

    metric = nxt["seven_day_metric"]
    lines.extend(
        [
            "",
            "## C. 下一步（单一最高优先级，已落地自动化）",
            "",
            f"- ID：`{nxt['id']}`",
            f"- Owner：{nxt['owner']}（GitHub `{nxt['owner_github']}`）",
            f"- 动作：{nxt['title']}",
            f"- 7 日指标：`{metric['name']}` — {metric['definition']}",
            f"- Continue：{nxt['continue_threshold']}",
            f"- Stop：{nxt['stop_threshold']}",
            f"- 下次复盘：{nxt['next_review_date']}",
            f"- 依据：{nxt['rationale']}",
            "",
            "## 局限",
            "",
        ]
    )
    for item in payload["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_ops_retrospective_artifacts(
    payload: dict[str, Any],
    *,
    json_path: Path | str,
    markdown_path: Path | str,
) -> None:
    json_file = Path(json_path)
    md_file = Path(markdown_path)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_file.write_text(render_ops_retrospective_markdown(payload), encoding="utf-8")
