"""Organic sprint phase 1: public OA/Zhihu packets only (no LLM, images, or publish).

Deterministic builders for:
  (A) 2026-08-17 WeChat 贴图 《柜机缺货先查这7步》
  (B) 2026-08-18 Zhihu scenario rewrite 《库存显示有货，为什么柜机还是缺货？》
  (C) WeChat welcome + single-keyword auto-reply「复盘表」

Never mutates WeChat/Zhihu external state. Never calls project external LLM APIs.
Never generates bitmaps (status = awaiting_antigravity_images).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse, parse_qs

from growth.combat_pack import CAMPAIGN, TOOL_PAGE_URL
from growth.wechat_stockout_draft import (
    assert_html_visible_text_chinese_only,
    assert_no_latin_visible,
    visible_text_from_html,
)

OPS_DATE = "2026-08-15"
PHASE = 1
IMAGE_STATUS = "awaiting_antigravity_images"
OWNER_GITHUB = "LoganWang123"
TIMEZONE_LABEL = "Asia/Shanghai"

WECHAT_TIEKU_PIECE_ID = "o1-wechat-stockout-tieku"
ZHIHU_SCENARIO_PIECE_ID = "o1-zhihu-inventory-stockout"
WECHAT_AUTOREPLY_PIECE_ID = "o1-wechat-autoreply-fupan"

WECHAT_TIEKU_TITLE = "柜机缺货先查这7步"
WECHAT_TIEKU_DATE = "2026-08-17"
ZHIHU_TITLE = "库存显示有货，为什么柜机还是缺货？"
ZHIHU_DATE = "2026-08-18"
KEYWORD_FUPAN = "复盘表"

CTA_BUTTON_TEXT = "打开智能柜周复盘工具页"
CTA_SUPPORT_ZH = (
    "打开智能柜周经营复盘工具页；订阅经营清单与预约运营商访谈入口在工具页内"
    "（人工跟进，不自动群发）"
)

FORBIDDEN_DISTRIBUTION = (
    "朋友圈",
    "微信群",
    "社群",
    "个人号私发",
    "私域群发",
    "一对一私发清单",
)

EXCEL_CLAIM_PATTERNS = (
    re.compile(r"excel", re.IGNORECASE),
    re.compile(r"xls[xm]?", re.IGNORECASE),
    re.compile(r"表格下载"),
    re.compile(r"下载.{0,8}表格"),
    re.compile(r"下载.{0,8}复盘表"),
    re.compile(r"附件下载"),
)

RAW_URL_RE = re.compile(r"https?://", re.IGNORECASE)
LATIN_TOKEN_RE = re.compile(r"[A-Za-z]+")
ZEROREALM_URL_RE = re.compile(r"https://zerorealm\.tech[^\s\"'<>\]\)]*")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utm(*, source: str, medium: str, content: str) -> str:
    return (
        f"utm_source={source}&utm_medium={medium}"
        f"&utm_campaign={CAMPAIGN}&utm_content={content}"
    )


def _cta_url(*, source: str, medium: str, content: str) -> str:
    return f"{TOOL_PAGE_URL}?{_utm(source=source, medium=medium, content=content)}"


def tracking_ids() -> dict[str, Any]:
    return {
        "campaign": CAMPAIGN,
        "tool_page": TOOL_PAGE_URL,
        "pieces": {
            WECHAT_TIEKU_PIECE_ID: {
                "utm_source": "wechat",
                "utm_medium": "image_post",
                "utm_content": "stockout_7steps_tieku",
                "tracking_id": "organic_20260817_wechat_tieku_stockout7",
            },
            ZHIHU_SCENARIO_PIECE_ID: {
                "utm_source": "zhihu",
                "utm_medium": "article",
                "utm_content": "inventory_vs_stockout_qa",
                "tracking_id": "organic_20260818_zhihu_inventory_stockout",
            },
            WECHAT_AUTOREPLY_PIECE_ID: {
                "welcome": {
                    "utm_source": "wechat",
                    "utm_medium": "auto_reply",
                    "utm_content": "wechat_welcome",
                    "tracking_id": "organic_wechat_welcome_fupan_tool",
                },
                "keyword": {
                    "keyword": KEYWORD_FUPAN,
                    "utm_source": "wechat",
                    "utm_medium": "auto_reply",
                    "utm_content": "wechat_kw_fupanbiao",
                    "tracking_id": "organic_wechat_kw_fupanbiao",
                },
            },
        },
    }


def continue_stop_metrics() -> dict[str, Any]:
    return {
        "window": {"start": "2026-08-15", "end": "2026-08-26", "tz": TIMEZONE_LABEL},
        "leading_only_while_channel_reports_stale": True,
        "continue_all_of": [
            {
                "id": "organic_pieces_on_dates",
                "rule": (
                    f"{WECHAT_TIEKU_DATE} 公众号贴图《{WECHAT_TIEKU_TITLE}》"
                    f"与 {ZHIHU_DATE} 知乎改写《{ZHIHU_TITLE}》均已人工发布"
                ),
            },
            {
                "id": "single_cta_compliance",
                "rule": "每条内容仅一个周复盘工具页行动入口，且带本条追踪参数",
            },
            {
                "id": "no_private_distribution",
                "rule": "未使用朋友圈、微信群/社群、个人号私发或私域群发",
            },
            {
                "id": "autoreply_no_excel_claim",
                "rule": "欢迎语与关键词「复盘表」均未声称可下载表格文件",
            },
            {
                "id": "solo_hours",
                "rule": "连续两周实际投入 ≤15 小时/周",
            },
        ],
        "stop_any_of": [
            {
                "id": "private_channel_used",
                "action": "立即停止该分发动作并回滚口径；本冲刺仅保留公众号与知乎公开面",
            },
            {
                "id": "second_cta_or_raw_url_visible_on_wechat",
                "action": "停止发布该稿；修正为中文可见文案 + 隐藏链接参数",
            },
            {
                "id": "excel_download_false_claim",
                "action": "停止自动回复上线；改为指向浏览器周复盘工具",
            },
            {
                "id": "fabricated_read_lift",
                "action": "渠道报表仍过期时，停止宣称阅读已提升",
            },
        ],
    }


def browser_handoff_instructions() -> dict[str, Any]:
    return {
        "phase1_mutates_external_state": False,
        "operator": OWNER_GITHUB,
        "steps": [
            {
                "order": 1,
                "surface": "wechat_oa_backend",
                "action": (
                    "浏览器打开公众号后台 → 自动回复："
                    "粘贴欢迎语与关键词「复盘表」配置包；"
                    "链接用后台超链接/菜单，勿把完整网址写成可见纯文本；"
                    "保存后自测关注与关键词，勿调用本仓发布接口。"
                ),
            },
            {
                "order": 2,
                "surface": "wechat_oa_image_post",
                "action": (
                    f"待 Antigravity 贴图位图就绪后，于 {WECHAT_TIEKU_DATE} "
                    f"人工发布《{WECHAT_TIEKU_TITLE}》；"
                    "仅公众号公开面；禁止朋友圈/群/私发。"
                ),
            },
            {
                "order": 3,
                "surface": "zhihu_editor",
                "action": (
                    f"于 {ZHIHU_DATE} 在知乎编辑器粘贴场景改写稿；"
                    "文末仅保留一个指向周复盘工具的中文锚点链接；人工发布。"
                ),
            },
            {
                "order": 4,
                "surface": "ledger",
                "action": (
                    "发布日记入 organic-only 排期与实验台账："
                    "是否单行动入口、是否禁用私域分发、图片状态。"
                ),
            },
        ],
        "antigravity": {
            "image_status": IMAGE_STATUS,
            "note": "Cursor 只准备 image briefs；位图由 Antigravity 生成并回写约定路径。",
        },
    }


def _compliance_block() -> dict[str, Any]:
    return {
        "fact_inference_opinion": (
            "口径为零域参考 / 企业内部实验口径，不是行业统一标准；"
            "文中区分事实、推断与观点。"
        ),
        "no_investment_advice": True,
        "no_fake_benchmarks": True,
        "no_second_cta": True,
        "no_raw_visible_urls_on_wechat": True,
        "wechat_visible_text_chinese_only": True,
        "no_excel_download_claim": True,
        "no_friends_circle": True,
        "no_groups": True,
        "no_personal_private_distribution": True,
        "organic_only": True,
        "single_campaign": CAMPAIGN,
        "tool_page": TOOL_PAGE_URL,
        "auto_publish": False,
        "llm_api_used": False,
        "external_state_mutated": False,
    }


def _image_brief(
    *,
    content_id: str,
    channel: str,
    purpose: str,
    title: str,
    width: int,
    height: int,
    aspect_ratio: str,
    overlay_title: str,
    overlay_subtitle: str,
    panel_index: int | None = None,
) -> dict[str, Any]:
    brief: dict[str, Any] = {
        "content_id": content_id,
        "channel": channel,
        "purpose": purpose,
        "status": IMAGE_STATUS,
        "aspect_ratio": aspect_ratio,
        "width": width,
        "height": height,
        "subject": f"零域研究贴图视觉：{title}",
        "must_include": [
            "智能柜 / 终端履约现场",
            "真实光照",
            "克制纪录片式商业摄影感",
        ],
        "must_avoid": [
            "虚构仪表盘百分比",
            "霓虹赛博风",
            "机器人手",
            "水印",
            "虚构品牌标识",
            "表情符号",
            "朋友圈九宫格私域暗示",
        ],
        "text_overlay": {
            "primary": overlay_title,
            "secondary": overlay_subtitle,
            "privacy_note": "浏览器本地计算 · 不上传",
        },
        "prompt_zh": (
            f"为「{title}」生成克制的智能柜运营贴图。"
            "场景围绕柜机补货、点位巡检或账实核对；"
            "专业真实，无科幻机器人，无霓虹科技风；"
            "若叠字仅用 brief 中文，勿虚构排名或行业均值。"
        ),
        "color_hint": "#2563EB 冷蓝白",
        "owner": "antigravity",
        "note": "Cursor 只准备 briefs；Antigravity 生成位图。",
    }
    if panel_index is not None:
        brief["panel_index"] = panel_index
    return brief


def wechat_tieku_step_captions() -> list[dict[str, str]]:
    """Seven checklist steps (caption/copy). Panels combine these into four frames."""
    return [
        {"step": "1", "caption": "先定性：是信号噪声，还是真实缺货"},
        {"step": "2", "caption": "核对库存口径与账实，先校正再加补"},
        {"step": "3", "caption": "确认是否畅销货品反复断货"},
        {"step": "4", "caption": "检查补货任务是否超时"},
        {"step": "5", "caption": "确认设备在线可售"},
        {"step": "6", "caption": "检查点位与货品是否错配"},
        {"step": "7", "caption": "选定主动作，并写下停止规则"},
    ]


def wechat_tieku_panel_overlays() -> list[dict[str, Any]]:
    """Exactly four vertical panels: steps 1-2, 3-4, 5-6, and 7."""
    return [
        {
            "panel_index": 1,
            "combined_steps": [1, 2],
            "overlay_title": "第1至2步",
            "overlay_subtitle": "先定性信号；核对账实再加补",
            "section": "先定性信号；核对账实再加补",
        },
        {
            "panel_index": 2,
            "combined_steps": [3, 4],
            "overlay_title": "第3至4步",
            "overlay_subtitle": "畅销反复断货；补货是否超时",
            "section": "畅销反复断货；补货是否超时",
        },
        {
            "panel_index": 3,
            "combined_steps": [5, 6],
            "overlay_title": "第5至6步",
            "overlay_subtitle": "设备在线可售；点位货品错配",
            "section": "设备在线可售；点位货品错配",
        },
        {
            "panel_index": 4,
            "combined_steps": [7],
            "overlay_title": "第7步",
            "overlay_subtitle": "选定主动作，写下停止规则",
            "section": "选定主动作，写下停止规则",
        },
    ]


def build_wechat_tieku_visible_caption() -> str:
    """Customer-visible WeChat 贴图 caption — Chinese only, no raw URL."""
    steps = "；".join(f"{s['step']}）{s['caption']}" for s in wechat_tieku_step_captions())
    return (
        f"【{WECHAT_TIEKU_TITLE}】\n"
        "柜机报警缺货，不等于立刻该补同一货品。先按七步排查，再决定补货、调货或复盘选品。\n"
        f"{steps}。\n"
        f"{CTA_SUPPORT_ZH}。\n"
        f"点这里：{CTA_BUTTON_TEXT}"
    )


def build_wechat_tieku_html_caption(*, cta_url: str) -> str:
    """HTML caption with single hidden href CTA for OA image-post handoff."""
    body = build_wechat_tieku_visible_caption().replace("\n", "<br/>")
    # Replace trailing plain CTA phrase with anchored button text (URL only in href).
    if not body.endswith(CTA_BUTTON_TEXT):
        raise ValueError("caption must end with approved Chinese CTA button text")
    prefix = body[: -len(CTA_BUTTON_TEXT)]
    return (
        f"<p>{prefix}"
        f'<a href="{cta_url}">{CTA_BUTTON_TEXT}</a></p>'
    )


def build_wechat_tieku_packet(*, body_markdown: str) -> dict[str, Any]:
    meta = tracking_ids()["pieces"][WECHAT_TIEKU_PIECE_ID]
    cta_url = _cta_url(
        source=meta["utm_source"],
        medium=meta["utm_medium"],
        content=meta["utm_content"],
    )
    excerpt = (
        "柜机缺货先别盲目加补。用七步分清信号与真实缺货，"
        "再决定补货、调货或进入选品复盘。"
    )
    tags = ["智能柜", "缺货", "补货", "运营清单", "周复盘"]
    caption = build_wechat_tieku_visible_caption()
    html_caption = build_wechat_tieku_html_caption(cta_url=cta_url)
    panels = wechat_tieku_panel_overlays()
    image_briefs = [
        _image_brief(
            content_id=WECHAT_TIEKU_PIECE_ID,
            channel="wechat",
            purpose="cover",
            title=WECHAT_TIEKU_TITLE,
            width=1080,
            height=1080,
            aspect_ratio="1:1",
            overlay_title=WECHAT_TIEKU_TITLE,
            overlay_subtitle="公开号贴图 · 七步排查",
        )
    ]
    for item in panels:
        image_briefs.append(
            _image_brief(
                content_id=WECHAT_TIEKU_PIECE_ID,
                channel="wechat",
                purpose="tieku_panel",
                title=WECHAT_TIEKU_TITLE,
                width=1080,
                height=1350,
                aspect_ratio="4:5",
                overlay_title=item["overlay_title"],
                overlay_subtitle=item["overlay_subtitle"],
                panel_index=int(item["panel_index"]),
            )
        )
    return {
        "schema_version": 1,
        "ops_date": OPS_DATE,
        "phase": PHASE,
        "piece_id": WECHAT_TIEKU_PIECE_ID,
        "channel": "wechat",
        "format": "image_post_tieku",
        "action": "production_ready_packet",
        "schedule_intent": {
            "publish_date": WECHAT_TIEKU_DATE,
            "tz": TIMEZONE_LABEL,
            "surface": "wechat_official_account_only",
            "forbidden_surfaces": list(FORBIDDEN_DISTRIBUTION),
            "auto_publish": False,
        },
        "status": "production_ready_awaiting_images",
        "title": WECHAT_TIEKU_TITLE,
        "excerpt": excerpt,
        "digest": excerpt[:54],
        "tags": tags,
        "platform_formatting": {
            "style": "wechat_image_post_tieku",
            "image_brief_count": 5,
            "panel_count": 4,
            "cover_aspect_ratio": "1:1",
            "panel_aspect_ratio": "4:5",
            "panel_step_groups": ["1-2", "3-4", "5-6", "7"],
            "caption_max_hint": "短文案 + 五图叠字（方封面+四竖屏合步）；可见文案仅中文",
            "cta_rendering": "single_anchor_button_no_raw_url",
            "sections": [p["section"] for p in panels],
            "wechat_notes": [
                "仅公众号公开贴图/图文",
                "禁止朋友圈、群、个人号私发",
                "人工审核后发布；本阶段不调用外部接口改状态",
            ],
        },
        "body_markdown": body_markdown,
        "visible_caption_zh": caption,
        "html_caption": html_caption,
        "cta": {
            "copy": CTA_SUPPORT_ZH,
            "button_text": CTA_BUTTON_TEXT,
            "url": cta_url,
            "utm": _utm(
                source=meta["utm_source"],
                medium=meta["utm_medium"],
                content=meta["utm_content"],
            ),
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "utm_content": meta["utm_content"],
            "tracking_id": meta["tracking_id"],
            "max_per_piece": 1,
        },
        "compliance": _compliance_block(),
        "image_briefs": image_briefs,
        "image_status": IMAGE_STATUS,
        "continue_stop_metrics_ref": "manifest.continue_stop_metrics",
        "browser_handoff_ref": "manifest.browser_handoff",
        "sources": [
            {
                "type": "organic_sprint",
                "ops_date": OPS_DATE,
                "piece_id": WECHAT_TIEKU_PIECE_ID,
            },
            {
                "type": "related_checklist",
                "note": "叙事对齐缺货七步清单，贴图为公开号短视觉版，非原文搬运",
            },
            {"type": "tool_page", "url": TOOL_PAGE_URL},
        ],
        "auto_publish": False,
        "llm_api_used": False,
        "external_state_mutated": False,
    }


def build_zhihu_scenario_packet(*, body_markdown: str) -> dict[str, Any]:
    meta = tracking_ids()["pieces"][ZHIHU_SCENARIO_PIECE_ID]
    cta_url = _cta_url(
        source=meta["utm_source"],
        medium=meta["utm_medium"],
        content=meta["utm_content"],
    )
    excerpt = (
        "后台库存显示有货，柜机却买不到，通常不是单一缺货问题。"
        "本文用场景拆解账实、同步、应售状态与补货时效，并给出最小动作。"
    )
    tags = ["智能柜", "缺货", "库存准确率", "无人零售", "运营"]
    return {
        "schema_version": 1,
        "ops_date": OPS_DATE,
        "phase": PHASE,
        "piece_id": ZHIHU_SCENARIO_PIECE_ID,
        "channel": "zhihu",
        "format": "scenario_qa_rewrite",
        "action": "production_ready_packet",
        "schedule_intent": {
            "publish_date": ZHIHU_DATE,
            "tz": TIMEZONE_LABEL,
            "surface": "zhihu_public_only",
            "forbidden_surfaces": list(FORBIDDEN_DISTRIBUTION),
            "auto_publish": False,
            "reuse_of": WECHAT_TIEKU_PIECE_ID,
        },
        "status": "production_ready_awaiting_images",
        "title": ZHIHU_TITLE,
        "excerpt": excerpt,
        "tags": tags,
        "topics": tags,
        "platform_formatting": {
            "style": "zhihu_scenario_rewrite",
            "not_verbatim_wechat_or_website": True,
            "attribution_note": "知乎账号级阅读无法做文章级归因",
            "cta_rendering": "single_markdown_anchor_no_raw_url_line",
            "sections": [
                "场景重述：库存有货 vs 柜机缺货",
                "常见原因分层（账实、同步、应售、履约）",
                "不可用小样本阅读波动下因果",
                "最小动作与周复盘回填",
                "唯一行动入口",
            ],
        },
        "body_markdown": body_markdown,
        "cta": {
            "copy": CTA_SUPPORT_ZH,
            "button_text": CTA_BUTTON_TEXT,
            "url": cta_url,
            "utm": _utm(
                source=meta["utm_source"],
                medium=meta["utm_medium"],
                content=meta["utm_content"],
            ),
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "utm_content": meta["utm_content"],
            "tracking_id": meta["tracking_id"],
            "max_per_piece": 1,
        },
        "compliance": {
            **_compliance_block(),
            "wechat_visible_text_chinese_only": False,
            "no_raw_visible_urls_on_wechat": False,
            "zhihu_no_raw_url_as_standalone_line": True,
        },
        "image_briefs": [
            _image_brief(
                content_id=ZHIHU_SCENARIO_PIECE_ID,
                channel="zhihu",
                purpose="cover",
                title=ZHIHU_TITLE,
                width=1200,
                height=675,
                aspect_ratio="16:9",
                overlay_title="库存有货 ≠ 柜机可买",
                overlay_subtitle="账实 · 同步 · 应售 · 补货时效",
            )
        ],
        "image_status": IMAGE_STATUS,
        "sources": [
            {
                "type": "organic_sprint",
                "ops_date": OPS_DATE,
                "piece_id": ZHIHU_SCENARIO_PIECE_ID,
                "reuse_of": WECHAT_TIEKU_PIECE_ID,
            },
            {"type": "tool_page", "url": TOOL_PAGE_URL},
        ],
        "auto_publish": False,
        "llm_api_used": False,
        "external_state_mutated": False,
    }


def _wechat_reply_html(paragraphs: list[str], *, cta_url: str) -> str:
    parts = [f"<p>{p}</p>" for p in paragraphs]
    parts.append(
        f'<p><a href="{cta_url}">{CTA_BUTTON_TEXT}</a></p>'
    )
    return "".join(parts)


def build_wechat_autoreply_packet() -> dict[str, Any]:
    track = tracking_ids()["pieces"][WECHAT_AUTOREPLY_PIECE_ID]
    welcome_meta = track["welcome"]
    keyword_meta = track["keyword"]
    welcome_url = _cta_url(
        source=welcome_meta["utm_source"],
        medium=welcome_meta["utm_medium"],
        content=welcome_meta["utm_content"],
    )
    keyword_url = _cta_url(
        source=keyword_meta["utm_source"],
        medium=keyword_meta["utm_medium"],
        content=keyword_meta["utm_content"],
    )

    welcome_paragraphs = [
        "欢迎关注零域研究。",
        "这里分享智能柜运营可执行清单与周复盘方法。",
        f"回复「{KEYWORD_FUPAN}」，获取智能柜周经营复盘工具入口"
        "（浏览器打开、本地计算，不上传经营数据）。",
        CTA_SUPPORT_ZH + "。",
    ]
    keyword_paragraphs = [
        "智能柜周经营复盘工具：按五个过程指标对照本周与上周。",
        "在浏览器打开即可填写；数值只在本地计算，刷新即清空。",
        "这不是表格文件派发，也不提供行业均值下载。",
        CTA_SUPPORT_ZH + "。",
    ]

    welcome_html = _wechat_reply_html(welcome_paragraphs, cta_url=welcome_url)
    keyword_html = _wechat_reply_html(keyword_paragraphs, cta_url=keyword_url)
    welcome_visible = "\n".join(welcome_paragraphs + [CTA_BUTTON_TEXT])
    keyword_visible = "\n".join(keyword_paragraphs + [CTA_BUTTON_TEXT])

    return {
        "schema_version": 1,
        "ops_date": OPS_DATE,
        "phase": PHASE,
        "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
        "channel": "wechat",
        "format": "oa_auto_reply_config",
        "action": "config_packet_browser_handoff_only",
        "schedule_intent": {
            "config_ready_date": OPS_DATE,
            "apply_via": "browser_oa_backend_manual",
            "tz": TIMEZONE_LABEL,
            "api_mutation_allowed": False,
            "forbidden_surfaces": list(FORBIDDEN_DISTRIBUTION),
        },
        "status": "production_ready_config",
        "title": "公众号欢迎语与关键词自动回复（复盘表）",
        "excerpt": (
            "中文欢迎语 + 唯一关键词「复盘表」自动回复，"
            "指向智能柜周经营复盘工具，不声称表格文件下载。"
        ),
        "tags": ["智能柜", "周复盘", "公众号", "自动回复"],
        "platform_formatting": {
            "style": "wechat_oa_auto_reply",
            "welcome_enabled": True,
            "keyword_match": "exact",
            "keywords": [KEYWORD_FUPAN],
            "keyword_count": 1,
            "cta_rendering": "single_anchor_per_reply_no_raw_url",
            "wechat_notes": [
                "可见文案仅中文",
                "每条回复仅一个工具页行动入口",
                "禁止声称可下载表格文件",
                "本阶段只交付配置包，不调用公众号接口写入",
            ],
        },
        "welcome_reply": {
            "visible_text_zh": welcome_visible,
            "html": welcome_html,
            "cta": {
                "button_text": CTA_BUTTON_TEXT,
                "url": welcome_url,
                "utm_content": welcome_meta["utm_content"],
                "tracking_id": welcome_meta["tracking_id"],
            },
        },
        "keyword_replies": [
            {
                "keyword": KEYWORD_FUPAN,
                "match": "exact",
                "visible_text_zh": keyword_visible,
                "html": keyword_html,
                "cta": {
                    "button_text": CTA_BUTTON_TEXT,
                    "url": keyword_url,
                    "utm_content": keyword_meta["utm_content"],
                    "tracking_id": keyword_meta["tracking_id"],
                },
            }
        ],
        "compliance": _compliance_block(),
        "image_briefs": [],
        "image_status": "not_applicable",
        "false_claim_guardrails": {
            "excel_download": False,
            "spreadsheet_attachment": False,
            "industry_benchmark_file": False,
            "stated_tool_behavior": "browser_local_weekly_review_tool",
        },
        "sources": [
            {"type": "tool_page", "url": TOOL_PAGE_URL},
            {
                "type": "organic_sprint",
                "ops_date": OPS_DATE,
                "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
            },
        ],
        "auto_publish": False,
        "llm_api_used": False,
        "external_state_mutated": False,
    }


def build_organic_only_schedule(
    *,
    wechat_packet: dict[str, Any],
    zhihu_packet: dict[str, Any],
    autoreply_packet: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "schedule_id": "organic_only_2026-08-15",
        "approved": True,
        "ops_date": OPS_DATE,
        "tz": TIMEZONE_LABEL,
        "distribution_policy": {
            "allowed": ["wechat_official_account", "zhihu_public"],
            "forbidden": list(FORBIDDEN_DISTRIBUTION),
            "friends_circle": False,
            "groups": False,
            "personal_private": False,
        },
        "experiment_continuity": {
            "ledger_label": "founder_14d_2026-08-13",
            "utm_campaign": CAMPAIGN,
            "tool_page": TOOL_PAGE_URL,
        },
        "calendar": [
            {
                "date": OPS_DATE,
                "channel": "wechat",
                "action": "prepare_autoreply_config_packet",
                "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
                "status": autoreply_packet["status"],
            },
            {
                "date": WECHAT_TIEKU_DATE,
                "channel": "wechat",
                "action": "publish_image_post_tieku",
                "piece_id": WECHAT_TIEKU_PIECE_ID,
                "title": WECHAT_TIEKU_TITLE,
                "status": wechat_packet["status"],
            },
            {
                "date": ZHIHU_DATE,
                "channel": "zhihu",
                "action": "publish_scenario_rewrite",
                "piece_id": ZHIHU_SCENARIO_PIECE_ID,
                "title": ZHIHU_TITLE,
                "status": zhihu_packet["status"],
            },
        ],
        "single_cta_rule": {
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "max_cta_per_piece": 1,
        },
        "image_status": IMAGE_STATUS,
        "external_state_mutated": False,
        "llm_api_used": False,
    }


def build_organic_experiment_ledger_update() -> dict[str, Any]:
    """Approved organic-only ledger overlay for the founder 14d experiment."""
    return {
        "schema_version": 1,
        "period": {
            "start": "2026-08-13",
            "end": "2026-08-26",
            "label": "founder_14d_2026-08-13",
        },
        "organic_only": True,
        "privacy": {
            "raw_reports_copied": False,
            "user_pii_recorded": False,
            "contents": "aggregates_and_manual_counts_only",
        },
        "distribution_policy": {
            "friends_circle": False,
            "groups": False,
            "personal_private": False,
            "allowed_surfaces": ["wechat_official_account", "zhihu_public"],
        },
        "funnel_manual": {
            "impressions": None,
            "views": None,
            "tool_views": 0,
            "subscribe_click": 0,
            "subscribe_success": 0,
            "interview_click": 0,
            "replies": 0,
            "interview_completed": 0,
            "public_case_permissions": 0,
        },
        "channel_observed": {
            "wechat_unique_readers": None,
            "wechat_overlapping_source_readers_sum": None,
            "wechat_share_people": None,
            "wechat_original_link_people": None,
            "zhihu_reads": None,
            "zhihu_engagement": None,
            "zhihu_article_level_attribution_available": False,
        },
        "organic_phase1": {
            "ops_date": OPS_DATE,
            "pieces": [
                {
                    "piece_id": WECHAT_TIEKU_PIECE_ID,
                    "date": WECHAT_TIEKU_DATE,
                    "title": WECHAT_TIEKU_TITLE,
                },
                {
                    "piece_id": ZHIHU_SCENARIO_PIECE_ID,
                    "date": ZHIHU_DATE,
                    "title": ZHIHU_TITLE,
                },
                {
                    "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
                    "keyword": KEYWORD_FUPAN,
                    "config_ready_date": OPS_DATE,
                },
            ],
        },
        "alerts": [],
        "notes": (
            "2026-08-15 organic sprint phase 1: public WeChat OA 贴图 + Zhihu rewrite + "
            "welcome/keyword「复盘表」config packets only. "
            "No朋友圈, no groups, no personal/private distribution. "
            "No external WeChat/Zhihu mutation in phase 1. "
            "Keep channel_observed null until freshness gate passes. "
            "Do not claim Excel download for the weekly-review tool."
        ),
    }


def build_phase1_manifest(
    *,
    wechat_packet: dict[str, Any],
    zhihu_packet: dict[str, Any],
    autoreply_packet: dict[str, Any],
    schedule: dict[str, Any],
    article_source_paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ops_date": OPS_DATE,
        "phase": PHASE,
        "sprint": "organic",
        "owner_github": OWNER_GITHUB,
        "tz": TIMEZONE_LABEL,
        "status": "phase1_packets_ready",
        "safety": {
            "publish": False,
            "mass_send": False,
            "friends_circle": False,
            "groups": False,
            "personal_private_distribution": False,
            "llm_api": False,
            "image_generation": False,
            "external_wechat_zhihu_mutation": False,
        },
        "packets": [
            {
                "piece_id": WECHAT_TIEKU_PIECE_ID,
                "channel": "wechat",
                "format": "image_post_tieku",
                "title": wechat_packet["title"],
                "publish_date": WECHAT_TIEKU_DATE,
                "cta_url": wechat_packet["cta"]["url"],
                "tracking_id": wechat_packet["cta"]["tracking_id"],
                "image_status": IMAGE_STATUS,
                "image_brief_count": 5,
                "panel_count": 4,
                "panel_step_groups": ["1-2", "3-4", "5-6", "7"],
                "packet_json": (
                    "data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json"
                ),
                "article_source": article_source_paths.get(WECHAT_TIEKU_PIECE_ID),
            },
            {
                "piece_id": ZHIHU_SCENARIO_PIECE_ID,
                "channel": "zhihu",
                "format": "scenario_qa_rewrite",
                "title": zhihu_packet["title"],
                "publish_date": ZHIHU_DATE,
                "cta_url": zhihu_packet["cta"]["url"],
                "tracking_id": zhihu_packet["cta"]["tracking_id"],
                "image_status": IMAGE_STATUS,
                "packet_json": (
                    "data/growth/"
                    "content-packet-o1-zhihu-inventory-stockout-2026-08-15.json"
                ),
                "article_source": article_source_paths.get(ZHIHU_SCENARIO_PIECE_ID),
            },
            {
                "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
                "channel": "wechat",
                "format": "oa_auto_reply_config",
                "title": autoreply_packet["title"],
                "keyword": KEYWORD_FUPAN,
                "image_status": "not_applicable",
                "packet_json": (
                    "data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json"
                ),
                "article_source": article_source_paths.get(WECHAT_AUTOREPLY_PIECE_ID),
            },
        ],
        "schedule_path": "data/growth/organic-only-schedule-2026-08-15.json",
        "ledger_path": "data/growth/organic-experiment-ledger-2026-08-15.json",
        "schedule_approved": bool(schedule.get("approved")),
        "tracking_ids": tracking_ids(),
        "continue_stop_metrics": continue_stop_metrics(),
        "browser_handoff": browser_handoff_instructions(),
        "single_cta_rule": {
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "max_cta_per_piece": 1,
        },
        "image_status": IMAGE_STATUS,
        "generated_at": _utc_now_iso(),
    }


def assert_no_excel_download_claim(text: str) -> None:
    for pattern in EXCEL_CLAIM_PATTERNS:
        if pattern.search(text or ""):
            # Allow explicit negation that we do NOT provide spreadsheet downloads.
            if re.search(r"不是表格文件|不提供.{0,6}下载|非表格文件", text or ""):
                if pattern.pattern.lower() in {"excel", r"xls[xm]?"}:
                    # Latin excel/xls must not appear in WeChat visible text anyway.
                    raise ValueError("WeChat visible text must not mention Excel/xls")
                continue
            raise ValueError(f"false Excel/download claim detected: {pattern.pattern}")


def assert_single_tool_cta(html_or_md: str, cta_url: str) -> None:
    if not cta_url.startswith(TOOL_PAGE_URL):
        raise ValueError("CTA must point at smart-cabinet weekly-review tool")
    parsed = urlparse(cta_url)
    qs = parse_qs(parsed.query)
    if qs.get("utm_campaign", [None])[0] != CAMPAIGN:
        raise ValueError("CTA missing approved campaign")
    found = ZEROREALM_URL_RE.findall(unescape(html_or_md))
    if found != [cta_url]:
        raise ValueError("piece must contain exactly one approved tool CTA URL")


def assert_no_forbidden_distribution(text: str) -> None:
    lowered = text or ""
    # Allow policy documents to name forbidden channels while forbidding intent to use them.
    intent = re.compile(
        r"(发|发到|转发到|同步到|铺到).{0,6}(朋友圈|微信群|社群|个人号)"
    )
    if intent.search(lowered):
        raise ValueError("private/friends-circle/group distribution intent detected")


def assert_wechat_visible_rules(*, title: str, visible_text: str, html: str, cta_url: str) -> None:
    assert_no_latin_visible(title, field="title")
    assert_no_latin_visible(visible_text, field="visible_text")
    assert_html_visible_text_chinese_only(html)
    if RAW_URL_RE.search(visible_text_from_html(html)):
        raise ValueError("raw URL visible in WeChat HTML")
    assert_single_tool_cta(html, cta_url)
    assert_no_excel_download_claim(visible_text)
    assert_no_excel_download_claim(visible_text_from_html(html))


def validate_wechat_tieku_packet(packet: dict[str, Any]) -> None:
    if packet["title"] != WECHAT_TIEKU_TITLE:
        raise ValueError("unexpected WeChat 贴图 title")
    if packet["schedule_intent"]["publish_date"] != WECHAT_TIEKU_DATE:
        raise ValueError("WeChat 贴图 date must be 2026-08-17")
    assert_wechat_visible_rules(
        title=packet["title"],
        visible_text=packet["visible_caption_zh"],
        html=packet["html_caption"],
        cta_url=packet["cta"]["url"],
    )
    assert_no_forbidden_distribution(packet["visible_caption_zh"])
    if packet["image_status"] != IMAGE_STATUS:
        raise ValueError("image status must be awaiting_antigravity_images")
    briefs = packet.get("image_briefs") or []
    if len(briefs) != 5:
        raise ValueError("WeChat 贴图 must have exactly 5 image briefs")
    cover, *panels = briefs
    if cover.get("purpose") != "cover" or cover.get("aspect_ratio") != "1:1":
        raise ValueError("first image brief must be square cover")
    if len(panels) != 4:
        raise ValueError("WeChat 贴图 must have exactly 4 vertical panels")
    for panel in panels:
        if panel.get("purpose") != "tieku_panel":
            raise ValueError("non-cover briefs must be tieku_panel")
        if panel.get("aspect_ratio") != "4:5":
            raise ValueError("tieku panels must be vertical 4:5")
        if panel.get("status") != IMAGE_STATUS:
            raise ValueError("panel status must be awaiting_antigravity_images")
    if cover.get("status") != IMAGE_STATUS:
        raise ValueError("cover status must be awaiting_antigravity_images")
    formatting = packet.get("platform_formatting") or {}
    if formatting.get("panel_count") != 4 or formatting.get("image_brief_count") != 5:
        raise ValueError("platform_formatting must declare 5 briefs / 4 panels")
    if formatting.get("panel_step_groups") != ["1-2", "3-4", "5-6", "7"]:
        raise ValueError("panel_step_groups must combine steps 1-2, 3-4, 5-6, 7")
    for brief in briefs:
        overlay = brief.get("text_overlay") or {}
        for key in ("primary", "secondary", "privacy_note"):
            assert_no_latin_visible(str(overlay.get(key) or ""), field=f"overlay.{key}")
    if packet.get("external_state_mutated") or packet.get("llm_api_used"):
        raise ValueError("phase1 packet must not mutate external state or call LLM")


def validate_zhihu_packet(packet: dict[str, Any]) -> None:
    if packet["title"] != ZHIHU_TITLE:
        raise ValueError("unexpected Zhihu title")
    if packet["schedule_intent"]["publish_date"] != ZHIHU_DATE:
        raise ValueError("Zhihu date must be 2026-08-18")
    body = packet["body_markdown"]
    assert_single_tool_cta(body, packet["cta"]["url"])
    # No standalone raw URL line.
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            raise ValueError("Zhihu body must not show a raw URL as its own line")
    if body.count(packet["cta"]["url"]) != 1:
        raise ValueError("Zhihu body must contain exactly one CTA URL")
    if packet["image_status"] != IMAGE_STATUS:
        raise ValueError("image status must be awaiting_antigravity_images")


def validate_autoreply_packet(packet: dict[str, Any]) -> None:
    keywords = [
        item["keyword"] for item in packet.get("keyword_replies") or []
    ]
    if keywords != [KEYWORD_FUPAN]:
        raise ValueError("exactly one keyword 复盘表 required")
    welcome = packet["welcome_reply"]
    assert_wechat_visible_rules(
        title="欢迎语",
        visible_text=welcome["visible_text_zh"],
        html=welcome["html"],
        cta_url=welcome["cta"]["url"],
    )
    kw = packet["keyword_replies"][0]
    assert_wechat_visible_rules(
        title="关键词回复",
        visible_text=kw["visible_text_zh"],
        html=kw["html"],
        cta_url=kw["cta"]["url"],
    )
    blob = welcome["visible_text_zh"] + "\n" + kw["visible_text_zh"]
    if re.search(r"下载", blob) and not re.search(r"不提供|不是表格文件", blob):
        raise ValueError("auto-reply must not imply a file download")
    if LATIN_TOKEN_RE.search(visible_text_from_html(welcome["html"])):
        raise ValueError("welcome visible text has Latin letters")


def validate_schedule(schedule: dict[str, Any]) -> None:
    if not schedule.get("approved"):
        raise ValueError("organic-only schedule must be approved")
    policy = schedule["distribution_policy"]
    if policy.get("friends_circle") or policy.get("groups") or policy.get("personal_private"):
        raise ValueError("private distribution flags must be false")
    dates = {row["date"]: row for row in schedule["calendar"]}
    if dates.get(WECHAT_TIEKU_DATE, {}).get("piece_id") != WECHAT_TIEKU_PIECE_ID:
        raise ValueError("schedule missing 2026-08-17 WeChat 贴图")
    if dates.get(ZHIHU_DATE, {}).get("piece_id") != ZHIHU_SCENARIO_PIECE_ID:
        raise ValueError("schedule missing 2026-08-18 Zhihu rewrite")


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").strip() + "\n"
    return re.sub(r"[ \t]+\n", "\n", text)
