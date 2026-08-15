"""Organic sprint phase 1: public OA/Zhihu packets only (no LLM, images, or publish).

Deterministic builders for:
  (A) 2026-08-17 WeChat 贴图 《柜机缺货先查这7步》
  (B) 2026-08-18 Zhihu scenario rewrite 《库存显示有货，为什么柜机还是缺货？》
  (C) WeChat welcome + single-keyword auto-reply「复盘表」

Never mutates WeChat/Zhihu external state. Never calls project external LLM APIs.
Never generates bitmaps (status = awaiting_antigravity_images).
"""

from __future__ import annotations

import json
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

# External platform lifecycle (draft ≠ scheduled/published).
STATUS_ASSETS_READY = "assets_ready"
STATUS_DRAFT_SAVED = "draft_saved"
STATUS_SCHEDULED = "scheduled"
STATUS_PUBLISHED = "published"
STATUS_BLOCKED = "blocked"
STATUS_CONFIGURED = "configured"
EXTERNAL_LIFECYCLE_STATUSES = frozenset(
    {
        STATUS_ASSETS_READY,
        STATUS_DRAFT_SAVED,
        STATUS_SCHEDULED,
        STATUS_PUBLISHED,
        STATUS_BLOCKED,
        STATUS_CONFIGURED,
    }
)

WECHAT_OA_ACCOUNT = "ZeroRealm零域AI"
ZHIHU_ACCOUNT = "ZeroRealm AI"
WECHAT_WELCOME_RULE_ID = "456828165"
WECHAT_KEYWORD_RULE_ID = "456844465"
WECHAT_TIEKU_APP_ID = "100000212"
WECHAT_TIEKU_DATA_SEQ = "4650538271616466946"
WECHAT_TIEKU_DRAFT_SAVED_AT = "2026-08-15T18:05:00+08:00"
WECHAT_TIEKU_SCHEDULE_ATTEMPT_AT = "2026-08-17T20:30:00+08:00"
WECHAT_BLOCK_REASON = "admin_qr_verification_required"
ZHIHU_DRAFT_ID = "2072013992894149965"
ZHIHU_PLANNED_WINDOW = "2026-08-18T20:30:00+08:00"

CTA_BUTTON_TEXT = "打开智能柜周复盘工具页"
CTA_SUPPORT_ZH = (
    "关注公众号后回复「复盘表」，自助打开智能柜周经营复盘工具；"
    "可在工具页公开订阅经营清单"
)

CONVERSION_FUNNEL_ZH = "公开内容 → 关注公众号 → 回复「复盘表」→ 自助使用周经营复盘工具"

PROFESSIONAL_BOUNDARIES_ZH = (
    "不使用现任公司内部经营数据、客户名单、未公开案例、内部流程截图、同事观点；"
    "不以雇主名义发言；示例仅用公开资料、合成数据或匿名通用场景。"
)

FORBIDDEN_CTA_TERMS = (
    "预约运营商访谈",
    "运营商访谈",
    "有效访谈",
    "交流线索",
    "有效运营商交流线索",
    "加微信",
    "一对一联系",
    "留下公司",
    "点位地址",
    "点位身份",
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
        "anonymous_observables": [
            {
                "id": "content_prep_on_time_rate",
                "rule": "计划内容按期准备率（草稿/配置就绪人工核对；未观测不填造）",
            },
            {
                "id": "keyword_replies",
                "rule": "关键词「复盘表」回复数（公众号后台人工计数；未观测保持 0）",
            },
            {
                "id": "tool_views",
                "rule": "工具页访问（网站 tool_view / 人工录入；未观测保持 0）",
            },
            {
                "id": "public_platform_engagement_delta",
                "rule": (
                    "公开平台收藏/赞同/阅读变化"
                    "（仅渠道报表新鲜时录入，否则保持 null，不虚构）"
                ),
            },
        ],
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
                "rule": (
                    "每条内容仅一个周复盘工具页行动入口（或引导回复「复盘表」），"
                    "且带本条追踪参数；无访谈 CTA"
                ),
            },
            {
                "id": "self_serve_funnel_only",
                "rule": CONVERSION_FUNNEL_ZH + "；可公开订阅，无一对一/加微信/访谈",
            },
            {
                "id": "professional_boundaries",
                "rule": PROFESSIONAL_BOUNDARIES_ZH,
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
                "id": "interview_or_one_to_one_cta",
                "action": "停止发布该稿；改为自助「复盘表」/工具页 CTA",
            },
            {
                "id": "employer_boundary_breach",
                "action": "下架或改正文案；删除内部数据/客户/未公开案例/同事观点痕迹",
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
        "browser_manual_ops_recorded": True,
        "operator": OWNER_GITHUB,
        "steps": [
            {
                "order": 1,
                "surface": "wechat_oa_backend",
                "status": STATUS_CONFIGURED,
                "action": (
                    "已核验：被关注回复与关键词「复盘表」精确匹配均已保存启用；"
                    "中文富文本链接，无原始网址可见。后续勿用本仓接口改写。"
                ),
            },
            {
                "order": 2,
                "surface": "wechat_oa_image_post",
                "status": STATUS_BLOCKED,
                "action": (
                    f"草稿《{WECHAT_TIEKU_TITLE}》已 draft_saved（5 图顺序完整）；"
                    f"定时 {WECHAT_TIEKU_SCHEDULE_ATTEMPT_AT} 因 "
                    f"{WECHAT_BLOCK_REASON} 阻塞并已安全退出。"
                    "勿记为 scheduled/published；仅公众号公开面；禁止朋友圈/群/私发。"
                ),
            },
            {
                "order": 3,
                "surface": "zhihu_editor",
                "status": STATUS_DRAFT_SAVED,
                "action": (
                    f"知乎草稿《{ZHIHU_TITLE}》已 draft_saved；"
                    f"网页端不支持定时；计划窗口 {ZHIHU_PLANNED_WINDOW}；未提前发布。"
                ),
            },
            {
                "order": 4,
                "surface": "ledger",
                "action": (
                    "已回写 organic-only 排期与实验台账："
                    "configured / draft_saved / blocked；草稿≠scheduled/published。"
                ),
            },
        ],
        "antigravity": {
            "image_status": "images_ready",
            "note": (
                "公众号贴图 5 张与知乎封面已由 Antigravity（gemini-3.7-flash-high）"
                "生成并验收 PASS；Cursor 仅回写路径/哈希/状态，不生成位图。"
            ),
        },
        "remaining_blockers": [
            {
                "piece_id": WECHAT_TIEKU_PIECE_ID,
                "reason": WECHAT_BLOCK_REASON,
            }
        ],
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
        "no_interview_cta": True,
        "no_one_to_one_contact_ask": True,
        "no_wechat_add_ask": True,
        "no_company_or_site_identity_ask": True,
        "conversion_funnel": CONVERSION_FUNNEL_ZH,
        "professional_boundaries_zh": PROFESSIONAL_BOUNDARIES_ZH,
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
        f"回复「{KEYWORD_FUPAN}」，即可自助打开智能柜周经营复盘工具"
        "（浏览器打开、本地计算，不上传经营数据）。",
        "可在工具页公开订阅经营清单。",
    ]
    keyword_paragraphs = [
        "智能柜周经营复盘工具：按五个过程指标对照本周与上周。",
        "在浏览器打开即可填写；数值只在本地计算，刷新即清空。",
        "这不是表格文件派发，也不提供行业均值下载。",
        "点下方入口自助使用；可公开订阅经营清单。",
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


def build_external_ops_verification() -> dict[str, Any]:
    """Verified browser-ops facts only; never records CDN/token/cookie secrets."""
    return {
        "verified_at": WECHAT_TIEKU_DRAFT_SAVED_AT,
        "via": "browser_manual",
        "repo_api_mutation": False,
        "privacy": {
            "cdn_urls_recorded": False,
            "login_tokens_recorded": False,
            "cookies_recorded": False,
            "raw_visible_urls_on_wechat": False,
        },
        "pieces": {
            WECHAT_AUTOREPLY_PIECE_ID: {
                "status": STATUS_CONFIGURED,
                "account": WECHAT_OA_ACCOUNT,
                "welcome": {
                    "status": STATUS_CONFIGURED,
                    "rule_id": WECHAT_WELCOME_RULE_ID,
                    "enabled": True,
                    "saved": True,
                    "link_style": "chinese_rich_text_no_raw_url",
                },
                "keyword": {
                    "keyword": KEYWORD_FUPAN,
                    "match": "exact",
                    "status": STATUS_CONFIGURED,
                    "rule_id": WECHAT_KEYWORD_RULE_ID,
                    "enabled": True,
                    "saved": True,
                    "link_style": "chinese_rich_text_no_raw_url",
                },
            },
            WECHAT_TIEKU_PIECE_ID: {
                "status": STATUS_BLOCKED,
                "assets_status": STATUS_ASSETS_READY,
                "draft_status": STATUS_DRAFT_SAVED,
                "schedule_status": STATUS_BLOCKED,
                "publish_status": "not_published",
                "account": WECHAT_OA_ACCOUNT,
                "title": WECHAT_TIEKU_TITLE,
                "app_id": WECHAT_TIEKU_APP_ID,
                "data_seq": WECHAT_TIEKU_DATA_SEQ,
                "image_count": 5,
                "image_order_complete": True,
                "saved_at": WECHAT_TIEKU_DRAFT_SAVED_AT,
                "scheduled": False,
                "published": False,
                "schedule_attempt": {
                    "intended_at": WECHAT_TIEKU_SCHEDULE_ATTEMPT_AT,
                    "result": STATUS_BLOCKED,
                    "block_reason": WECHAT_BLOCK_REASON,
                    "exited_safely": True,
                },
            },
            ZHIHU_SCENARIO_PIECE_ID: {
                "status": STATUS_DRAFT_SAVED,
                "assets_status": STATUS_ASSETS_READY,
                "draft_status": STATUS_DRAFT_SAVED,
                "schedule_status": "unsupported_on_web",
                "publish_status": "not_published",
                "account": ZHIHU_ACCOUNT,
                "title": ZHIHU_TITLE,
                "draft_id": ZHIHU_DRAFT_ID,
                "verified_fields": [
                    "title",
                    "cover",
                    "body",
                    "table",
                    "single_cta",
                ],
                "scheduled": False,
                "published": False,
                "planned_publish_window": ZHIHU_PLANNED_WINDOW,
                "note": (
                    "知乎网页端不支持文章定时；计划窗口已记录，未提前发布。"
                ),
            },
        },
        "blockers": [
            {
                "piece_id": WECHAT_TIEKU_PIECE_ID,
                "reason": WECHAT_BLOCK_REASON,
                "detail": (
                    f"尝试设置 {WECHAT_TIEKU_SCHEDULE_ATTEMPT_AT} 定时时触发管理员扫码验证，"
                    "已安全退出；草稿仍为 draft_saved，未 scheduled/published。"
                ),
            }
        ],
    }


def build_organic_only_schedule(
    *,
    wechat_packet: dict[str, Any],
    zhihu_packet: dict[str, Any],
    autoreply_packet: dict[str, Any],
    external_ops: dict[str, Any] | None = None,
) -> dict[str, Any]:
# Calendar lifecycle comes from verified external_ops; packet args keep API stable.
    _ = (
        wechat_packet.get("status"),
        zhihu_packet.get("status"),
        autoreply_packet.get("status"),
    )
    ops = external_ops or build_external_ops_verification()
    autoreply_status = ops["pieces"][WECHAT_AUTOREPLY_PIECE_ID]["status"]
    wechat_status = ops["pieces"][WECHAT_TIEKU_PIECE_ID]["status"]
    zhihu_status = ops["pieces"][ZHIHU_SCENARIO_PIECE_ID]["status"]
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
                "action": "configure_autoreply",
                "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
                "status": autoreply_status,
            },
            {
                "date": WECHAT_TIEKU_DATE,
                "channel": "wechat",
                "action": "publish_image_post_tieku",
                "piece_id": WECHAT_TIEKU_PIECE_ID,
                "title": WECHAT_TIEKU_TITLE,
                "status": wechat_status,
                "draft_status": STATUS_DRAFT_SAVED,
                "assets_status": STATUS_ASSETS_READY,
                "scheduled": False,
                "published": False,
                "block_reason": WECHAT_BLOCK_REASON,
            },
            {
                "date": ZHIHU_DATE,
                "channel": "zhihu",
                "action": "publish_scenario_rewrite",
                "piece_id": ZHIHU_SCENARIO_PIECE_ID,
                "title": ZHIHU_TITLE,
                "status": zhihu_status,
                "draft_status": STATUS_DRAFT_SAVED,
                "assets_status": STATUS_ASSETS_READY,
                "scheduled": False,
                "published": False,
                "planned_publish_window": ZHIHU_PLANNED_WINDOW,
            },
        ],
        "single_cta_rule": {
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "max_cta_per_piece": 1,
        },
        "image_status": "images_ready",
        "external_ops": ops,
        "external_state_mutated": False,
        "llm_api_used": False,
    }


def build_organic_experiment_ledger_update() -> dict[str, Any]:
    """Approved organic-only ledger overlay for the founder 14d experiment."""
    external_ops = build_external_ops_verification()
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
            "keyword_replies": 0,
            "subscribe_click": 0,
            "subscribe_success": 0,
        },
        "anonymous_metrics": {
            "content_prep_on_time_rate": None,
            "keyword_replies": 0,
            "tool_views": 0,
            "public_platform_favorites_delta": None,
            "public_platform_likes_delta": None,
            "public_platform_reads_delta": None,
        },
        "experiment_targets": {
            "content_prep_on_time_rate": (
                "计划内容按期准备率（草稿/配置就绪人工核对；未观测不填造）"
            ),
            "keyword_replies": "关键词「复盘表」回复数（公众号后台人工计数；未观测保持 0）",
            "tool_views": "工具页访问（网站 tool_view / 人工录入；未观测保持 0）",
            "public_platform_engagement_delta": (
                "公开平台收藏/赞同/阅读变化（仅渠道报表新鲜时录入，否则保持 null，不虚构）"
            ),
        },
        "conversion_funnel": CONVERSION_FUNNEL_ZH,
        "professional_boundaries_zh": PROFESSIONAL_BOUNDARIES_ZH,
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
            "external_ops": external_ops,
            "pieces": [
                {
                    "piece_id": WECHAT_TIEKU_PIECE_ID,
                    "date": WECHAT_TIEKU_DATE,
                    "title": WECHAT_TIEKU_TITLE,
                    "status": STATUS_BLOCKED,
                    "assets_status": STATUS_ASSETS_READY,
                    "draft_status": STATUS_DRAFT_SAVED,
                    "scheduled": False,
                    "published": False,
                    "block_reason": WECHAT_BLOCK_REASON,
                    "app_id": WECHAT_TIEKU_APP_ID,
                    "data_seq": WECHAT_TIEKU_DATA_SEQ,
                    "saved_at": WECHAT_TIEKU_DRAFT_SAVED_AT,
                },
                {
                    "piece_id": ZHIHU_SCENARIO_PIECE_ID,
                    "date": ZHIHU_DATE,
                    "title": ZHIHU_TITLE,
                    "status": STATUS_DRAFT_SAVED,
                    "assets_status": STATUS_ASSETS_READY,
                    "draft_status": STATUS_DRAFT_SAVED,
                    "scheduled": False,
                    "published": False,
                    "draft_id": ZHIHU_DRAFT_ID,
                    "account": ZHIHU_ACCOUNT,
                    "planned_publish_window": ZHIHU_PLANNED_WINDOW,
                },
                {
                    "piece_id": WECHAT_AUTOREPLY_PIECE_ID,
                    "keyword": KEYWORD_FUPAN,
                    "config_ready_date": OPS_DATE,
                    "status": STATUS_CONFIGURED,
                    "account": WECHAT_OA_ACCOUNT,
                    "welcome_rule_id": WECHAT_WELCOME_RULE_ID,
                    "keyword_rule_id": WECHAT_KEYWORD_RULE_ID,
                },
            ],
        },
        "alerts": [
            {
                "id": "wechat_tieku_admin_qr_block",
                "severity": "ops",
                "piece_id": WECHAT_TIEKU_PIECE_ID,
                "reason": WECHAT_BLOCK_REASON,
                "message": (
                    "微信贴图草稿已保存但定时被管理员扫码验证阻塞；"
                    "勿将 draft_saved 记为 scheduled/published。"
                ),
            }
        ],
        "notes": (
            "2026-08-15 organic sprint phase 1: public WeChat OA 贴图 + Zhihu rewrite + "
            "welcome/keyword「复盘表」. "
            "Conversion: 公开内容 → 关注公众号 → 回复「复盘表」→ 自助周复盘工具. "
            "No interview / one-to-one / WeChat-add / company-site identity asks. "
            f"Professional boundaries: {PROFESSIONAL_BOUNDARIES_ZH} "
            "Browser manual ops verified: autoreply configured; WeChat 贴图 draft_saved "
            f"but schedule blocked ({WECHAT_BLOCK_REASON}); Zhihu draft_saved "
            f"(planned {ZHIHU_PLANNED_WINDOW}, web has no article schedule). "
            "No朋友圈, no groups, no personal/private distribution. "
            "No CDN/token/cookie recorded. "
            "Anonymous metrics only; keep channel deltas null until freshness gate passes. "
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
    external_ops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ops = external_ops or build_external_ops_verification()
    wechat_ext = ops["pieces"][WECHAT_TIEKU_PIECE_ID]
    zhihu_ext = ops["pieces"][ZHIHU_SCENARIO_PIECE_ID]
    autoreply_ext = ops["pieces"][WECHAT_AUTOREPLY_PIECE_ID]
    return {
        "schema_version": 1,
        "ops_date": OPS_DATE,
        "phase": PHASE,
        "sprint": "organic",
        "owner_github": OWNER_GITHUB,
        "tz": TIMEZONE_LABEL,
        "status": "phase1_external_ops_recorded",
        "safety": {
            "publish": False,
            "mass_send": False,
            "friends_circle": False,
            "groups": False,
            "personal_private_distribution": False,
            "llm_api": False,
            "image_generation": False,
            "external_wechat_zhihu_mutation": False,
            "browser_manual_ops": True,
            "cdn_urls_recorded": False,
            "tokens_recorded": False,
            "cookies_recorded": False,
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
                "image_status": "images_ready",
                "external_status": wechat_ext["status"],
                "assets_status": wechat_ext["assets_status"],
                "draft_status": wechat_ext["draft_status"],
                "scheduled": False,
                "published": False,
                "block_reason": wechat_ext["schedule_attempt"]["block_reason"],
                "app_id": wechat_ext["app_id"],
                "data_seq": wechat_ext["data_seq"],
                "saved_at": wechat_ext["saved_at"],
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
                "image_status": "images_ready",
                "external_status": zhihu_ext["status"],
                "assets_status": zhihu_ext["assets_status"],
                "draft_status": zhihu_ext["draft_status"],
                "scheduled": False,
                "published": False,
                "draft_id": zhihu_ext["draft_id"],
                "account": zhihu_ext["account"],
                "planned_publish_window": zhihu_ext["planned_publish_window"],
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
                "external_status": autoreply_ext["status"],
                "account": autoreply_ext["account"],
                "welcome_rule_id": autoreply_ext["welcome"]["rule_id"],
                "keyword_rule_id": autoreply_ext["keyword"]["rule_id"],
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
        "external_ops": ops,
        "single_cta_rule": {
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "max_cta_per_piece": 1,
        },
        "image_status": "images_ready",
        "generated_at": _utc_now_iso(),
    }


def assert_no_forbidden_cta_terms(text: str) -> None:
    blob = text or ""
    for term in FORBIDDEN_CTA_TERMS:
        if term in blob:
            raise ValueError(f"forbidden CTA/outreach term detected: {term}")


def assert_professional_boundaries_declared(compliance: dict[str, Any]) -> None:
    if not compliance.get("professional_boundaries_zh"):
        raise ValueError("professional boundaries must be declared")
    if compliance.get("no_interview_cta") is not True:
        raise ValueError("no_interview_cta must be true")
    if compliance.get("no_one_to_one_contact_ask") is not True:
        raise ValueError("no_one_to_one_contact_ask must be true")
    if compliance.get("no_wechat_add_ask") is not True:
        raise ValueError("no_wechat_add_ask must be true")
    if compliance.get("no_company_or_site_identity_ask") is not True:
        raise ValueError("no_company_or_site_identity_ask must be true")
    boundaries = str(compliance.get("professional_boundaries_zh") or "")
    for needle in (
        "内部经营数据",
        "客户名单",
        "未公开案例",
        "内部流程截图",
        "同事观点",
        "不以雇主名义",
    ):
        if needle not in boundaries:
            raise ValueError(f"professional boundaries missing: {needle}")


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
    assert_no_forbidden_cta_terms(visible_text)
    assert_no_forbidden_cta_terms(visible_text_from_html(html))


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
    assert_no_forbidden_cta_terms(packet.get("cta", {}).get("copy") or "")
    assert_no_forbidden_cta_terms(packet.get("body_markdown") or "")
    assert_professional_boundaries_declared(packet.get("compliance") or {})
    if packet["image_status"] not in (IMAGE_STATUS, "images_ready"):
        raise ValueError(
            "image status must be awaiting_antigravity_images or images_ready"
        )
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
        if panel.get("status") not in (IMAGE_STATUS, "images_ready"):
            raise ValueError(
                "panel status must be awaiting_antigravity_images or images_ready"
            )
    if cover.get("status") not in (IMAGE_STATUS, "images_ready"):
        raise ValueError(
            "cover status must be awaiting_antigravity_images or images_ready"
        )
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
    assert_no_forbidden_cta_terms(body)
    assert_no_forbidden_cta_terms(packet.get("cta", {}).get("copy") or "")
    assert_professional_boundaries_declared(packet.get("compliance") or {})
    if packet["image_status"] not in (IMAGE_STATUS, "images_ready"):
        raise ValueError("image status must be awaiting_antigravity_images or images_ready")


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
    assert_no_forbidden_cta_terms(blob)
    assert_professional_boundaries_declared(packet.get("compliance") or {})
    if KEYWORD_FUPAN not in welcome["visible_text_zh"]:
        raise ValueError("welcome must guide reply 复盘表")


def validate_external_ops(ops: dict[str, Any]) -> None:
    privacy = ops.get("privacy") or {}
    for key in ("cdn_urls_recorded", "login_tokens_recorded", "cookies_recorded"):
        if privacy.get(key) is not False:
            raise ValueError(f"external_ops.privacy.{key} must be false")
    pieces = ops.get("pieces") or {}
    for piece_id in (
        WECHAT_AUTOREPLY_PIECE_ID,
        WECHAT_TIEKU_PIECE_ID,
        ZHIHU_SCENARIO_PIECE_ID,
    ):
        if piece_id not in pieces:
            raise ValueError(f"external_ops missing piece {piece_id}")
    autoreply = pieces[WECHAT_AUTOREPLY_PIECE_ID]
    if autoreply.get("status") != STATUS_CONFIGURED:
        raise ValueError("autoreply external status must be configured")
    if autoreply.get("welcome", {}).get("rule_id") != WECHAT_WELCOME_RULE_ID:
        raise ValueError("welcome rule_id mismatch")
    if autoreply.get("keyword", {}).get("rule_id") != WECHAT_KEYWORD_RULE_ID:
        raise ValueError("keyword rule_id mismatch")
    if autoreply.get("keyword", {}).get("match") != "exact":
        raise ValueError("keyword match must be exact")
    wechat = pieces[WECHAT_TIEKU_PIECE_ID]
    if wechat.get("status") != STATUS_BLOCKED:
        raise ValueError("WeChat 贴图 overall status must be blocked")
    if wechat.get("draft_status") != STATUS_DRAFT_SAVED:
        raise ValueError("WeChat 贴图 draft_status must be draft_saved")
    if wechat.get("assets_status") != STATUS_ASSETS_READY:
        raise ValueError("WeChat 贴图 assets_status must be assets_ready")
    if wechat.get("scheduled") or wechat.get("published"):
        raise ValueError("WeChat 贴图 draft must not be marked scheduled/published")
    if wechat.get("status") in (STATUS_SCHEDULED, STATUS_PUBLISHED):
        raise ValueError("WeChat 贴图 must not use scheduled/published as overall status")
    if wechat.get("app_id") != WECHAT_TIEKU_APP_ID:
        raise ValueError("WeChat 贴图 app_id mismatch")
    if wechat.get("data_seq") != WECHAT_TIEKU_DATA_SEQ:
        raise ValueError("WeChat 贴图 data_seq mismatch")
    if wechat.get("image_count") != 5 or not wechat.get("image_order_complete"):
        raise ValueError("WeChat 贴图 must record 5 images in order")
    attempt = wechat.get("schedule_attempt") or {}
    if attempt.get("block_reason") != WECHAT_BLOCK_REASON:
        raise ValueError("WeChat schedule block_reason mismatch")
    if not attempt.get("exited_safely"):
        raise ValueError("schedule attempt must record safe exit")
    zhihu = pieces[ZHIHU_SCENARIO_PIECE_ID]
    if zhihu.get("status") != STATUS_DRAFT_SAVED:
        raise ValueError("Zhihu status must be draft_saved")
    if zhihu.get("scheduled") or zhihu.get("published"):
        raise ValueError("Zhihu draft must not be marked scheduled/published")
    if zhihu.get("status") in (STATUS_SCHEDULED, STATUS_PUBLISHED):
        raise ValueError("Zhihu must not use scheduled/published as status")
    if zhihu.get("draft_id") != ZHIHU_DRAFT_ID:
        raise ValueError("Zhihu draft_id mismatch")
    if zhihu.get("planned_publish_window") != ZHIHU_PLANNED_WINDOW:
        raise ValueError("Zhihu planned window mismatch")
    blob = json_dumps_safe(ops).lower()
    # Forbid recording live secret material; allow boolean privacy flags named *cookie*.
    if "cdn.weixin" in blob or "cdn.zhihu" in blob:
        raise ValueError("forbidden CDN host recorded in external_ops")
    for needle in ("access_token=", "session_token=", "bearer ", "set-cookie:"):
        if needle in blob:
            raise ValueError(f"forbidden secret-like token recorded: {needle}")
    # Reject non-false privacy flags already checked; also reject long opaque token blobs.
    if '"cookie":' in blob or '"cookies":' in blob:
        raise ValueError("must not record cookie values in external_ops")


def json_dumps_safe(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


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
    wechat_row = dates[WECHAT_TIEKU_DATE]
    zhihu_row = dates[ZHIHU_DATE]
    autoreply_row = dates.get(OPS_DATE) or {}
    if wechat_row.get("status") in (STATUS_SCHEDULED, STATUS_PUBLISHED):
        raise ValueError("WeChat calendar row must not be scheduled/published while blocked")
    if wechat_row.get("status") != STATUS_BLOCKED:
        raise ValueError("WeChat calendar status must be blocked")
    if wechat_row.get("scheduled") or wechat_row.get("published"):
        raise ValueError("WeChat calendar flags scheduled/published must be false")
    if zhihu_row.get("status") in (STATUS_SCHEDULED, STATUS_PUBLISHED):
        raise ValueError("Zhihu calendar row must not be scheduled/published")
    if zhihu_row.get("status") != STATUS_DRAFT_SAVED:
        raise ValueError("Zhihu calendar status must be draft_saved")
    if zhihu_row.get("scheduled") or zhihu_row.get("published"):
        raise ValueError("Zhihu calendar flags scheduled/published must be false")
    if autoreply_row.get("status") != STATUS_CONFIGURED:
        raise ValueError("autoreply calendar status must be configured")
    if "external_ops" in schedule:
        validate_external_ops(schedule["external_ops"])


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").strip() + "\n"
    return re.sub(r"[ \t]+\n", "\n", text)
