"""14-day founder combat pack (deterministic, no auto-publish)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


CAMPAIGN = "founder14d_20260813"
HOURS_PER_WEEK_RANGE = (8, 15)
TOOL_PAGE_URL = "https://zerorealm.tech/tools/smart-cabinet-weekly-review"
CTA_COPY = (
    "关注公众号后回复「复盘表」，自助打开智能柜周经营复盘工具；"
    "可在工具页公开订阅经营清单"
)


def _utm(*, source: str, content: str) -> str:
    return (
        f"utm_source={source}&utm_medium=article"
        f"&utm_campaign={CAMPAIGN}&utm_content={content}"
    )


def _cta_url(utm_query: str) -> str:
    return f"{TOOL_PAGE_URL}?{utm_query}"


def _piece(
    *,
    piece_id: str,
    channel: str,
    publish_date: str,
    title: str,
    audience: str,
    search_intent: str,
    structure: list[str],
    utm_content: str,
    reuse_of: str | None,
    estimated_hours: float,
    theme: str,
) -> dict[str, Any]:
    utm = _utm(source=channel, content=utm_content)
    cta_url = _cta_url(utm)
    return {
        "id": piece_id,
        "channel": channel,
        "publish_date": publish_date,
        "title": title,
        "audience": audience,
        "search_intent": search_intent,
        "structure": structure,
        "cta": CTA_COPY,
        "cta_url": cta_url,
        "tool_page": TOOL_PAGE_URL,
        "utm": utm,
        "cross_channel_reuse_of": reuse_of,
        "estimated_hours": estimated_hours,
        "theme": theme,
        "auto_publish": False,
    }


def build_combat_pack(*, start_date: str = "2026-08-13") -> dict[str, Any]:
    """Build a 14-day pack sized for a solo founder (8–15h/week)."""
    start = date.fromisoformat(start_date)
    end = start + timedelta(days=13)
    week1_end = start + timedelta(days=6)
    week2_start = start + timedelta(days=7)

    audience = "智能柜运营商 / 运营负责人（单人创始人可执行）"

    pieces = [
        _piece(
            piece_id="w1-wechat-five-metrics",
            channel="wechat",
            publish_date=(start + timedelta(days=1)).isoformat(),  # Fri 08-14
            title="智能柜周经营复盘：先填这五个过程指标",
            audience=audience,
            search_intent="智能柜 周复盘 过程指标 / 柜机经营表",
            structure=[
                "开场：为什么不能只盯 GMV",
                "五指标定义与填写频率（内部实验口径，非行业基准）",
                "一页空白复盘表 + 填写示例",
                "本周最小动作：选 3–5 台柜填完",
                f"CTA URL（可复制）：见本条 cta_url；{CTA_COPY}",
            ],
            utm_content="five_metrics_weekly",
            reuse_of=None,
            estimated_hours=3.0,
            theme="五指标周复盘工具",
        ),
        _piece(
            piece_id="w1-zhihu-five-metrics",
            channel="zhihu",
            publish_date=(start + timedelta(days=2)).isoformat(),  # Sat 08-15
            title="智能柜运营商每周该盯哪五个过程指标？",
            audience=audience,
            search_intent="智能柜运营 看什么指标 / 柜机复盘",
            structure=[
                "问题重述与适用范围",
                "五指标问答式拆解（改写自微信工具文，非原文搬运）",
                "说明：知乎账号级阅读无法做文章级归因",
                f"CTA URL（可复制）：见本条 cta_url；{CTA_COPY}",
            ],
            utm_content="five_metrics_qa",
            reuse_of="w1-wechat-five-metrics",
            estimated_hours=1.5,
            theme="五指标周复盘工具",
        ),
        _piece(
            piece_id="w1-wechat-stockout",
            channel="wechat",
            publish_date=(start + timedelta(days=5)).isoformat(),  # Tue 08-18
            title="柜机缺货排查清单：先查这 7 步再补货",
            audience=audience,
            search_intent="智能柜 缺货率 排查 / 补货清单",
            structure=[
                "缺货信号 vs 真实缺货",
                "7 步排查（库存口径、补货时效、SKU、点位）",
                "可打印清单",
                "停止规则：连续两周同 SKU 缺货仍不调货则复盘选品",
                f"CTA URL（可复制）：见本条 cta_url；{CTA_COPY}",
            ],
            utm_content="stockout_checklist",
            reuse_of=None,
            estimated_hours=3.0,
            theme="缺货排查",
        ),
        _piece(
            piece_id="w2-wechat-decision",
            channel="wechat",
            publish_date=(week2_start + timedelta(days=1)).isoformat(),  # Fri 08-21
            title="智能柜运营决策清单：本周只拍板三件事",
            audience=audience,
            search_intent="智能柜 运营决策 清单 / 柜机本周动作",
            structure=[
                "决策清单模板（保留/调货/撤点）",
                "每项所需证据与停止规则",
                "与五指标复盘表、缺货清单的衔接",
                f"CTA URL（可复制）：见本条 cta_url；{CTA_COPY}",
            ],
            utm_content="ops_decision_checklist",
            reuse_of=None,
            estimated_hours=3.0,
            theme="运营决策清单",
        ),
        _piece(
            piece_id="w2-zhihu-stockout",
            channel="zhihu",
            publish_date=(week2_start + timedelta(days=2)).isoformat(),  # Sat 08-22
            title="智能柜老是缺货，补货前该先查什么？",
            audience=audience,
            search_intent="智能柜 缺货 怎么办 / 补货前检查",
            structure=[
                "问答改写自微信缺货排查文",
                "强调不可用小样本日阅读波动下因果结论",
                f"CTA URL（可复制）：见本条 cta_url；{CTA_COPY}",
            ],
            utm_content="stockout_qa",
            reuse_of="w1-wechat-stockout",
            estimated_hours=1.5,
            theme="缺货排查",
        ),
        _piece(
            piece_id="w2-wechat-reuse-decision",
            channel="wechat",
            publish_date=(week2_start + timedelta(days=5)).isoformat(),  # Tue 08-25
            title="把周复盘表用进决策：一张清单结束本周",
            audience=audience,
            search_intent="智能柜 周复盘 决策 / 经营清单",
            structure=[
                "五指标 → 缺货排查 → 决策清单串联示例",
                "14 天实验目标复盘提示（内部目标）",
                f"CTA URL（可复制）：见本条 cta_url；{CTA_COPY}",
            ],
            utm_content="metrics_to_decision",
            reuse_of="w2-wechat-decision",
            estimated_hours=2.5,
            theme="运营决策清单",
        ),
    ]

    rituals = [
        {
            "id": "week1-review",
            "date": week1_end.isoformat(),
            "title": "第 1 周复盘（60–90 分钟）",
            "checklist": [
                "只读“全部”唯一阅读，不把搜一搜/推荐相加",
                "记录知乎账号日阅读，标注缺文章级归因",
                "更新当期台账：内容按期准备率、关键词「复盘表」回复数、"
                "工具页访问、公开平台收藏/赞同/阅读变化；禁止用基线人数当漏斗分母",
                "不从小样本波动推因果；只决定下周是否继续清单文",
            ],
            "estimated_hours": 1.5,
        },
        {
            "id": "week2-review",
            "date": end.isoformat(),
            "title": "第 2 周复盘 + 14 天实验收口（90–120 分钟）",
            "checklist": [
                "对照可匿名观测的内部实验目标（非行业基准）",
                "漏斗零/缺失分母槽位标为 n/a，不当成 0%",
                "核对职业边界：未使用现任公司内部数据/客户名单/未公开案例",
                "决定下一轮 14 天是否沿用公开内容 → 复盘表 → 自助工具链路",
            ],
            "estimated_hours": 2.0,
        },
    ]

    self_serve_ops_hours_per_week = 2.5
    content_hours = sum(p["estimated_hours"] for p in pieces)
    ritual_hours = sum(r["estimated_hours"] for r in rituals)
    self_serve_ops_hours = self_serve_ops_hours_per_week * 2
    total_hours = content_hours + ritual_hours + self_serve_ops_hours

    return {
        "schema_version": 1,
        "pack_id": CAMPAIGN,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "tool_page_url": TOOL_PAGE_URL,
        "hours_budget_per_week": {
            "min": HOURS_PER_WEEK_RANGE[0],
            "max": HOURS_PER_WEEK_RANGE[1],
        },
        "estimated_total_hours_14d": round(total_hours, 1),
        "estimated_hours_per_week": round(total_hours / 2, 1),
        "within_solo_founder_budget": HOURS_PER_WEEK_RANGE[0]
        <= (total_hours / 2)
        <= HOURS_PER_WEEK_RANGE[1],
        "themes": ["五指标周复盘工具", "缺货排查", "运营决策清单"],
        "rules": [
            "不自动发布、不自动群发；全部人工审核后发布。",
            "不从小样本推因果；知乎无文章级归因时只看账号趋势。",
            "微信来源阅读可重叠，不可当唯一人数。",
            "目标为内部实验目标，不是行业基准。",
            "总量适配单人创始人每周 8–15 小时。",
            "转化链路：公开内容 → 关注公众号 → 回复「复盘表」→ 自助周复盘工具；"
            "允许公开订阅，禁止一对一联系/加微信/访谈/索取公司或点位身份。",
            "职业边界：不使用现任公司内部经营数据、客户名单、未公开案例、"
            "内部流程截图、同事观点；不以雇主名义发言；"
            "示例仅用公开资料、合成数据或匿名通用场景。",
            f"每条内容 CTA 使用可复制 URL，指向 {TOOL_PAGE_URL} 并带本条 UTM；"
            "唯一行动为回复「复盘表」或打开自助工具。",
        ],
        "pieces": pieces,
        "rituals": rituals,
        "hour_breakdown": {
            "content_production": content_hours,
            "weekly_reviews": ritual_hours,
            "self_serve_ops": self_serve_ops_hours,
        },
    }


def render_combat_pack_markdown(pack: dict[str, Any]) -> str:
    lines = [
        f"# 14 天创始人增长作战包（{pack['start_date']} ~ {pack['end_date']}）",
        "",
        f"> 预估总工时 **{pack['estimated_total_hours_14d']}h**"
        f"（约 **{pack['estimated_hours_per_week']}h/周**），"
        f"预算区间 {pack['hours_budget_per_week']['min']}–"
        f"{pack['hours_budget_per_week']['max']}h/周。"
        "不自动发布；不从小样本推因果。",
        f"工具页：`{pack.get('tool_page_url', TOOL_PAGE_URL)}`"
        "（回复「复盘表」或打开自助工具；可公开订阅）。",
        "",
        "## 规则",
        "",
    ]
    for rule in pack["rules"]:
        lines.append(f"- {rule}")

    lines.extend(["", "## 内容排期", ""])
    for piece in pack["pieces"]:
        lines.extend(
            [
                f"### {piece['publish_date']} · {piece['channel']} · {piece['title']}",
                "",
                f"- ID: `{piece['id']}`",
                f"- 主题: {piece['theme']}",
                f"- 受众: {piece['audience']}",
                f"- 搜索意图: {piece['search_intent']}",
                f"- CTA 文案: {piece['cta']}",
                f"- CTA URL（可复制）: `{piece['cta_url']}`",
                f"- UTM: `{piece['utm']}`",
                f"- 跨渠道复用自: {piece['cross_channel_reuse_of'] or '—'}",
                f"- 预估工时: {piece['estimated_hours']}h",
                f"- 自动发布: {piece['auto_publish']}",
                "- 结构:",
            ]
        )
        for step in piece["structure"]:
            lines.append(f"  - {step}")
        lines.append("")

    lines.extend(["", "## 周复盘仪式", ""])
    for ritual in pack["rituals"]:
        lines.append(f"### {ritual['date']} · {ritual['title']}")
        lines.append("")
        for item in ritual["checklist"]:
            lines.append(f"- [ ] {item}")
        lines.append(f"- 预估工时: {ritual['estimated_hours']}h")
        lines.append("")

    lines.extend(
        [
            "## 工时拆分",
            "",
            f"- 内容生产: {pack['hour_breakdown']['content_production']}h",
            f"- 周复盘: {pack['hour_breakdown']['weekly_reviews']}h",
            f"- 自助转化运营: {pack['hour_breakdown']['self_serve_ops']}h",
            "",
        ]
    )
    return "\n".join(lines)
