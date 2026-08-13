"""Build privacy-safe channel growth baselines and markdown reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from growth.wechat import WechatTendencySummary, parse_wechat_tendency_xls
from growth.zhihu import ZhihuDailySummary, parse_zhihu_daily_csv


@dataclass(frozen=True)
class GrowthExperiment:
    name: str
    hypothesis: str
    actions: list[str]
    metrics: list[str]
    targets: dict[str, str]


def _classify_title(title: str) -> str:
    if "日报" in title:
        return "daily_digest"
    if any(token in title for token in ("表", "指标", "清单", "复盘", "先查", "该盯")):
        return "tool_checklist"
    if any(token in title for token in ("？", "?", "下一站", "不是")):
        return "question_framing"
    if "研究" in title or "产业链" in title:
        return "research"
    return "other"


def _evidence_from_wechat(wechat: WechatTendencySummary) -> dict[str, Any]:
    ranking = wechat.title_unique_ranking
    by_type: dict[str, list[int]] = {}
    for item in ranking:
        by_type.setdefault(_classify_title(item.title), []).append(item.unique_readers)

    type_averages = {
        name: round(sum(values) / len(values), 2) if values else 0.0
        for name, values in sorted(by_type.items())
    }
    top_titles = [
        {"title": item.title, "unique_readers": item.unique_readers}
        for item in ranking[:5]
    ]
    return {
        "title_type_average_unique_readers": type_averages,
        "top_unique_titles": top_titles,
        "search_and_recommend_share_of_unique": {
            "搜一搜": wechat.overlapping_source_readers.get("搜一搜", 0),
            "推荐": wechat.overlapping_source_readers.get("推荐", 0),
            "unique_全部": wechat.unique_readers,
        },
    }


def default_experiments(wechat: WechatTendencySummary, zhihu: ZhihuDailySummary) -> list[GrowthExperiment]:
    evidence = _evidence_from_wechat(wechat)
    averages = evidence["title_type_average_unique_readers"]
    tool_avg = averages.get("tool_checklist", 0)
    daily_avg = averages.get("daily_digest", 0)

    return [
        GrowthExperiment(
            name="14天经营工具/清单优先实验",
            hypothesis=(
                f"在当前小样本中，工具/清单类标题“全部”阅读均值约 {tool_avg}，"
                f"高于泛日报类约 {daily_avg}；优先该类内容更可能抬升唯一阅读与搜一搜进入。"
            ),
            actions=[
                "每周至少发布 3 篇智能柜经营工具/清单/过程指标文，减少纯资讯堆砌的泛日报。",
                "标题与导语显式包含可执行动作（先查/复盘/清单/阈值），并保留问题型钩子。",
                "文末固定 CTA：订阅经营清单 / 提交纠错 / 预约运营商访谈。",
            ],
            metrics=[
                "微信“全部”唯一阅读人数（不可用来源相加替代）",
                "搜一搜与推荐来源阅读人数（重叠归因，仅作结构观察）",
                "分享人数、阅读原文人数",
                "知乎账号日阅读与非零阅读日数",
            ],
            targets={
                "wechat_unique_readers_14d": "相对本基线周均提升 ≥20%（小样本，仅作实验目标）",
                "wechat_share_or_original_link": "14天内分享+阅读原文合计 ≥ 8",
                "zhihu_nonzero_read_days": "14天内非零阅读日 ≥ 10",
                "cta_events": "订阅/纠错/访谈意向合计 ≥ 5（人工计数）",
            },
        ),
        GrowthExperiment(
            name="跨渠道问题型内容复用实验",
            hypothesis=(
                f"知乎样本总阅读 {zhihu.total_reads}、峰值日 {zhihu.peak_date}="
                f"{zhihu.peak_reads}，但缺文章级归因；将微信高表现问题/工具文改写到知乎，"
                "用于观察账号级阅读是否同步抬升，而非证明单篇因果。"
            ),
            actions=[
                "挑选微信“全部”阅读 Top3 中的工具/问题文，改写为知乎问答或短文并互链订阅 CTA。",
                "停止把泛日报原文原样搬运作为主增长手段。",
                "每日记录知乎阅读，但不对单日波动下因果结论。",
            ],
            metrics=[
                "知乎14天总阅读、峰值阅读、互动合计（赞/藏/分享）",
                "微信对应标题是否仍维持搜一搜/推荐结构",
            ],
            targets={
                "zhihu_reads_14d": "≥ 350（相对本基线窗口 305 的温和抬升目标）",
                "zhihu_engagement_14d": "赞+藏+分享合计 ≥ 12",
            },
        ),
    ]


def build_channel_baseline(
    *,
    wechat_path: Path | str,
    zhihu_path: Path | str,
    baseline_date: str = "2026-08-12",
    generated_on: str | None = None,
) -> dict[str, Any]:
    wechat = parse_wechat_tendency_xls(wechat_path)
    zhihu = parse_zhihu_daily_csv(zhihu_path)
    evidence = _evidence_from_wechat(wechat)
    experiments = default_experiments(wechat, zhihu)

    return {
        "schema_version": 1,
        "baseline_date": baseline_date,
        "generated_on": generated_on or date.today().isoformat(),
        "privacy": {
            "raw_reports_copied": False,
            "user_pii_recorded": False,
            "contents": "aggregates_only",
        },
        "limitations": [
            "样本很小：微信约30天、知乎约18天日汇总，不足以支持稳健因果推断。",
            "微信来源阅读人数可重叠，禁止把来源行相加当作唯一用户。",
            "知乎缺文章级归因，只能看账号级趋势，不能下单篇因果结论。",
            "本基线仅用于设定实验与复盘对照，不是增长成功证明。",
        ],
        "wechat": wechat.to_dict(),
        "zhihu": zhihu.to_dict(),
        "evidence_signals": evidence,
        "experiments_14d": [
            {
                "name": item.name,
                "hypothesis": item.hypothesis,
                "actions": item.actions,
                "metrics": item.metrics,
                "targets": item.targets,
            }
            for item in experiments
        ],
        "source_inputs": {
            "wechat_filename": Path(wechat_path).name,
            "zhihu_filename": Path(zhihu_path).name,
            "note": "仅记录文件名便于复现，不入库原始报表内容。",
        },
    }


def render_baseline_markdown(baseline: dict[str, Any]) -> str:
    wechat = baseline["wechat"]
    zhihu = baseline["zhihu"]
    sources = wechat["overlapping_source_readers"]
    engagement = wechat["engagement"]
    lines: list[str] = [
        f"# 渠道增长数据基线（{baseline['baseline_date']}）",
        "",
        "> 本报告只含聚合指标。未复制原始报表，未记录用户个人信息。"
        "样本小、知乎缺文章级归因，不能下因果结论。",
        "",
        "## 口径声明",
        "",
        "- 微信 **“全部”阅读人数** = 去重后的唯一阅读者。",
        "- 搜一搜 / 推荐 / 主页等来源阅读人数 **可重叠**，禁止相加当作唯一用户。",
        "- 知乎为账号级日汇总，无文章级归因。",
        "",
        "## 微信公众号（聚合）",
        "",
        f"- 统计周期：{wechat['period']['start']} ~ {wechat['period']['end']}",
        f"- 全部（唯一）阅读人数：**{wechat['unique_readers_全部']}**",
        f"- 搜一搜（可重叠）：**{sources.get('搜一搜', 0)}**",
        f"- 推荐（可重叠）：**{sources.get('推荐', 0)}**",
        f"- 公众号主页（可重叠）：**{sources.get('公众号主页', 0)}**",
        f"- 分享人数：**{engagement['share_people']}**",
        f"- 阅读原文人数：**{engagement['original_link_people']}**",
        f"- 收藏人数：**{engagement['favorite_people']}**",
        f"- 发表篇数：**{engagement['published_articles']}**",
        "",
        "### 逐标题“全部”阅读排名",
        "",
        "| 排名 | 标题 | 发表日期 | 全部阅读人数 |",
        "| --- | --- | --- | ---: |",
    ]
    for idx, item in enumerate(wechat["title_unique_ranking"], start=1):
        lines.append(
            f"| {idx} | {item['title']} | {item['publish_date']} | {item['unique_readers']} |"
        )

    lines.extend(
        [
            "",
            "## 知乎（账号级日汇总）",
            "",
            f"- 统计周期：{zhihu['period']['start']} ~ {zhihu['period']['end']}",
            f"- 阅读合计：**{zhihu['totals']['reads']}**",
            f"- 点赞合计：**{zhihu['totals']['likes']}**",
            f"- 收藏合计：**{zhihu['totals']['favorites']}**",
            f"- 分享合计：**{zhihu['totals']['shares']}**",
            f"- 评论合计：**{zhihu['totals']['comments']}**",
            f"- 非零阅读日：**{zhihu['nonzero_read_days']}**",
            f"- 峰值日：**{zhihu['peak']['date']}**，阅读 **{zhihu['peak']['reads']}**",
            "",
            "## 证据信号（描述性，非因果）",
            "",
        ]
    )
    averages = baseline["evidence_signals"]["title_type_average_unique_readers"]
    for name, value in averages.items():
        lines.append(f"- 标题类型 `{name}` 的“全部”阅读均值：{value}")

    lines.extend(["", "## 14 天增长实验（基于证据，含可量化目标）", ""])
    for experiment in baseline["experiments_14d"]:
        lines.append(f"### {experiment['name']}")
        lines.append("")
        lines.append(f"- 假设：{experiment['hypothesis']}")
        lines.append("- 动作：")
        for action in experiment["actions"]:
            lines.append(f"  - {action}")
        lines.append("- 观测指标：")
        for metric in experiment["metrics"]:
            lines.append(f"  - {metric}")
        lines.append("- 量化目标：")
        for key, value in experiment["targets"].items():
            lines.append(f"  - `{key}`: {value}")
        lines.append("")

    lines.extend(["## 局限", ""])
    for item in baseline["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_baseline_artifacts(
    baseline: dict[str, Any],
    *,
    json_path: Path | str,
    markdown_path: Path | str,
) -> None:
    json_file = Path(json_path)
    md_file = Path(markdown_path)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_file.write_text(render_baseline_markdown(baseline), encoding="utf-8")
