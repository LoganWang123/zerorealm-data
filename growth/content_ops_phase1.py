"""Phase-1 content ops: draft overlap helpers + production packet builders.

Deterministic only — does not call project LLM APIs, WeChat publish, or image gen.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from growth.combat_pack import CAMPAIGN, CTA_COPY, TOOL_PAGE_URL, build_combat_pack

PHASE1_DATE = "2026-08-15"
ZHIHU_PIECE_ID = "w1-zhihu-five-metrics"
WECHAT_STOCKOUT_PIECE_ID = "w1-wechat-stockout"
IMAGE_STATUS = "awaiting_antigravity_images"

# Titles / keywords used to detect overlap with the approved CEO plan.
PLAN_TITLE_HINTS: dict[str, list[str]] = {
    "w1-wechat-five-metrics": [
        "五个过程指标",
        "五指标",
        "周经营复盘",
        "周复盘",
    ],
    "w1-zhihu-five-metrics": [
        "五个过程指标",
        "每周该盯",
    ],
    "w1-wechat-stockout": [
        "缺货排查",
        "缺货清单",
        "7 步",
        "七步",
        "再补货",
    ],
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def summarize_draft_item(item: dict[str, Any]) -> dict[str, Any]:
    """Reduce a WeChat draft/batchget item to title/update/media status only."""
    media_id = str(item.get("media_id") or "")
    update_time = item.get("update_time")
    content = item.get("content") or {}
    news_items = content.get("news_item") or []
    articles: list[dict[str, Any]] = []
    for news in news_items:
        thumb = news.get("thumb_media_id") or news.get("thumb_url") or ""
        articles.append(
            {
                "title": str(news.get("title") or "").strip(),
                "author": str(news.get("author") or "").strip(),
                "digest": str(news.get("digest") or "").strip()[:160],
                "has_thumb_media": bool(thumb),
                "thumb_media_id_present": bool(news.get("thumb_media_id")),
                "show_cover_pic": news.get("show_cover_pic"),
                "update_time": news.get("update_time") or update_time,
            }
        )
    titles = [a["title"] for a in articles if a["title"]]
    return {
        "media_id": media_id,
        "update_time": update_time,
        "article_count": len(articles),
        "titles": titles,
        "articles": articles,
        "media_status": {
            "any_thumb_present": any(a["has_thumb_media"] for a in articles),
            "all_thumbs_present": bool(articles)
            and all(a["has_thumb_media"] for a in articles),
        },
    }


def match_plan_overlap(titles: list[str]) -> list[dict[str, Any]]:
    """Map draft titles to approved plan piece_ids via keyword overlap."""
    hits: list[dict[str, Any]] = []
    joined = " ".join(titles)
    for piece_id, hints in PLAN_TITLE_HINTS.items():
        matched = [h for h in hints if h in joined]
        if matched:
            hits.append(
                {
                    "piece_id": piece_id,
                    "matched_hints": matched,
                    "titles": titles,
                }
            )
    return hits


def inspect_draft_payload(api_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a safe inspection report from draft/batchget JSON (no bodies stored)."""
    items = api_payload.get("item") or []
    drafts = [summarize_draft_item(item) for item in items]
    overlaps: list[dict[str, Any]] = []
    for draft in drafts:
        for hit in match_plan_overlap(draft["titles"]):
            overlaps.append(
                {
                    "media_id": draft["media_id"],
                    "update_time": draft["update_time"],
                    **hit,
                }
            )
    return {
        "inspected_at": _utc_now_iso(),
        "ops_date": PHASE1_DATE,
        "mode": "read_only_list",
        "safety": {
            "delete": False,
            "overwrite": False,
            "publish": False,
            "mass_send": False,
            "llm_api": False,
            "image_generation": False,
        },
        "total_count": api_payload.get("total_count", len(drafts)),
        "item_count": api_payload.get("item_count", len(drafts)),
        "drafts": drafts,
        "plan_overlap": overlaps,
        "unknown_draft_policy": (
            "Never delete, overwrite, publish, or mass-send unknown drafts. "
            "Human review required before any mutation."
        ),
    }


def _piece_from_combat(piece_id: str) -> dict[str, Any]:
    pack = build_combat_pack(start_date="2026-08-13")
    for piece in pack["pieces"]:
        if piece["id"] == piece_id:
            return piece
    raise KeyError(f"piece not found in combat pack: {piece_id}")


def _compliance_block() -> dict[str, Any]:
    return {
        "fact_inference_opinion": (
            "Definitions are ZeroRealm reference / internal experiment口径; "
            "not industry benchmarks. Mark FACT/INFERENCE/OPINION explicitly in copy."
        ),
        "no_investment_advice": True,
        "no_fake_benchmarks": True,
        "no_second_cta": True,
        "single_campaign": CAMPAIGN,
        "tool_page": TOOL_PAGE_URL,
        "auto_publish": False,
        "llm_api_used": False,
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
) -> dict[str, Any]:
    return {
        "content_id": content_id,
        "channel": channel,
        "purpose": purpose,
        "status": IMAGE_STATUS,
        "aspect_ratio": aspect_ratio,
        "width": width,
        "height": height,
        "subject": f"ZeroRealm research visual for: {title}",
        "must_include": [
            "smart retail cabinet / terminal context",
            "realistic lighting",
            "documentary editorial look",
        ],
        "must_avoid": [
            "fake dashboards or invented percentages",
            "neon cyberpunk AI tropes",
            "robot hands",
            "watermark",
            "invented brand logos",
            "emoji",
        ],
        "text_overlay": {
            "primary": overlay_title,
            "secondary": overlay_subtitle,
            "privacy_note": "浏览器本地计算 · 不上传",
        },
        "prompt_zh": (
            f"为「{title}」生成克制的商业研究配图。"
            "场景围绕智能柜、便利零售或办公点位履约。"
            "专业真实，无科幻机器人，无霓虹科技风；"
            "若需要文字仅按 brief 叠加，勿虚构百分比或排名。"
        ),
        "color_hint": "#2563EB cool blue-white",
        "owner": "antigravity",
        "note": "Cursor prepares briefs only; Antigravity generates bitmaps.",
    }


def build_zhihu_five_metrics_packet(*, body_markdown: str) -> dict[str, Any]:
    piece = _piece_from_combat(ZHIHU_PIECE_ID)
    excerpt = (
        "智能柜运营商若只盯 GMV，往往错过更早暴露的经营质量信号。"
        "本文用问答方式拆解缺货率、补货及时率、设备在线率、SKU 动销率与库存准确率"
        "——ZeroRealm 参考口径，非行业统一标准。"
    )
    tags = [
        "智能柜",
        "无人零售",
        "运营指标",
        "缺货率",
        "周复盘",
    ]
    return {
        "schema_version": 1,
        "ops_date": PHASE1_DATE,
        "phase": 1,
        "piece_id": ZHIHU_PIECE_ID,
        "channel": "zhihu",
        "action": "publish_ready_packet",
        "status": "production_ready_awaiting_images",
        "title": piece["title"],
        "excerpt": excerpt,
        "tags": tags,
        "topics": tags,
        "platform_formatting": {
            "style": "zhihu_qa_rewrite",
            "not_verbatim_website_or_wechat": True,
            "attribution_note": "知乎账号级阅读无法做文章级归因",
            "sections": piece["structure"],
        },
        "body_markdown": body_markdown,
        "cta": {
            "copy": CTA_COPY,
            "url": piece["cta_url"],
            "utm": piece["utm"],
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "utm_content": "five_metrics_qa",
        },
        "compliance": _compliance_block(),
        "image_briefs": [
            _image_brief(
                content_id=ZHIHU_PIECE_ID,
                channel="zhihu",
                purpose="cover",
                title=piece["title"],
                width=1200,
                height=675,
                aspect_ratio="16:9",
                overlay_title="智能柜周经营复盘表",
                overlay_subtitle="五个过程指标：缺货 · 补货及时 · 在线 · 动销 · 库存准确",
            )
        ],
        "image_status": IMAGE_STATUS,
        "sources": [
            {
                "type": "website_mdx",
                "path": (
                    "zerorealm-website/content/insight/"
                    "smart-cabinet-five-process-metrics.mdx"
                ),
                "role": "rewrite_source_not_verbatim",
            },
            {
                "type": "combat_pack",
                "piece_id": ZHIHU_PIECE_ID,
                "reuse_of": "w1-wechat-five-metrics",
            },
            {
                "type": "ceo_plan",
                "path": "docs/reports/ceo-publish-distribution-plan-2026-08-15.md",
                "date": PHASE1_DATE,
            },
            {
                "type": "tool_page",
                "url": TOOL_PAGE_URL,
            },
        ],
        "auto_publish": False,
        "llm_api_used": False,
    }


def build_wechat_stockout_packet(*, body_markdown: str) -> dict[str, Any]:
    piece = _piece_from_combat(WECHAT_STOCKOUT_PIECE_ID)
    excerpt = (
        "柜机报警缺货，不等于立刻该补同一货品。"
        "先用 7 步区分信号与真实缺货，再决定补货、调货或复盘选品；"
        "含可打印勾选清单与停止规则。"
    )
    tags = ["智能柜", "缺货率", "补货", "运营清单", "周复盘"]
    return {
        "schema_version": 1,
        "ops_date": PHASE1_DATE,
        "phase": 1,
        "piece_id": WECHAT_STOCKOUT_PIECE_ID,
        "channel": "wechat",
        "action": "draft_ready_packet",
        "planned_draft_date": "2026-08-17",
        "planned_publish_date": "2026-08-18",
        "status": "production_ready_awaiting_images",
        "title": piece["title"],
        "excerpt": excerpt,
        "digest": excerpt[:120],
        "tags": tags,
        "platform_formatting": {
            "style": "wechat_checklist_article",
            "include_printable_checklist": True,
            "include_stop_rule": True,
            "sections": piece["structure"],
            "wechat_notes": [
                "draft-only until human review",
                "do not freepublish or mass-send from automation",
            ],
        },
        "body_markdown": body_markdown,
        "cta": {
            "copy": CTA_COPY,
            "url": piece["cta_url"],
            "utm": piece["utm"],
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "utm_content": "stockout_checklist",
        },
        "compliance": _compliance_block(),
        "image_briefs": [
            _image_brief(
                content_id=WECHAT_STOCKOUT_PIECE_ID,
                channel="wechat",
                purpose="cover",
                title=piece["title"],
                width=900,
                height=383,
                aspect_ratio="900:383",
                overlay_title="柜机缺货排查清单",
                overlay_subtitle="先查这 7 步再补货",
            ),
            _image_brief(
                content_id=WECHAT_STOCKOUT_PIECE_ID,
                channel="wechat",
                purpose="illustration",
                title=piece["title"],
                width=1280,
                height=720,
                aspect_ratio="16:9",
                overlay_title="缺货信号 ≠ 真实缺货",
                overlay_subtitle="库存口径 · 补货时效 · SKU · 点位",
            ),
        ],
        "image_status": IMAGE_STATUS,
        "sources": [
            {
                "type": "combat_pack",
                "piece_id": WECHAT_STOCKOUT_PIECE_ID,
            },
            {
                "type": "ceo_plan",
                "path": "docs/reports/ceo-publish-distribution-plan-2026-08-15.md",
                "draft_date": "2026-08-17",
                "publish_date": "2026-08-18",
            },
            {
                "type": "metric_dictionary",
                "refs": ["stockout-rate", "replenish-ontime-rate", "inventory-accuracy"],
            },
            {
                "type": "tool_page",
                "url": TOOL_PAGE_URL,
            },
        ],
        "auto_publish": False,
        "llm_api_used": False,
    }


def build_phase1_manifest(
    *,
    inspection: dict[str, Any],
    zhihu_packet: dict[str, Any],
    wechat_packet: dict[str, Any],
    article_source_paths: dict[str, str],
) -> dict[str, Any]:
    five_metrics_wechat_overlap = [
        o
        for o in inspection.get("plan_overlap", [])
        if o.get("piece_id") == "w1-wechat-five-metrics"
    ]
    return {
        "schema_version": 1,
        "ops_date": PHASE1_DATE,
        "phase": 1,
        "owner_github": "LoganWang123",
        "status": "phase1_packets_ready",
        "safety": inspection.get("safety"),
        "wechat_draft_inspection": {
            "total_count": inspection.get("total_count"),
            "item_count": inspection.get("item_count"),
            "overlap_count": len(inspection.get("plan_overlap") or []),
            "five_metrics_wechat_draft_present": bool(five_metrics_wechat_overlap),
            "report_json": "data/growth/wechat-draft-inspection-2026-08-15.json",
            "report_md": "docs/reports/wechat-draft-inspection-2026-08-15.md",
        },
        "packets": [
            {
                "piece_id": ZHIHU_PIECE_ID,
                "channel": "zhihu",
                "title": zhihu_packet["title"],
                "cta_url": zhihu_packet["cta"]["url"],
                "image_status": IMAGE_STATUS,
                "packet_json": (
                    "data/growth/content-packet-w1-zhihu-five-metrics-2026-08-15.json"
                ),
                "article_source": article_source_paths.get(ZHIHU_PIECE_ID),
            },
            {
                "piece_id": WECHAT_STOCKOUT_PIECE_ID,
                "channel": "wechat",
                "title": wechat_packet["title"],
                "cta_url": wechat_packet["cta"]["url"],
                "image_status": IMAGE_STATUS,
                "packet_json": (
                    "data/growth/content-packet-w1-wechat-stockout-2026-08-15.json"
                ),
                "article_source": article_source_paths.get(WECHAT_STOCKOUT_PIECE_ID),
            },
        ],
        "single_cta_rule": {
            "tool_page": TOOL_PAGE_URL,
            "campaign": CAMPAIGN,
            "max_cta_per_article": 1,
        },
        "exceptions": {
            "if_w1_wechat_five_metrics_unpublished": (
                "On 2026-08-15 prioritize WeChat five-metrics publish; "
                "defer Zhihu rewrite to 2026-08-16 per CEO plan."
            )
        },
        "generated_at": _utc_now_iso(),
    }


def strip_body_from_packet_for_dist(packet: dict[str, Any]) -> dict[str, Any]:
    """Optional lighter view — keep body in committed packet JSON for sources."""
    return packet


_MULTI_SPACE = re.compile(r"[ \t]+\n")


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").strip() + "\n"
    return _MULTI_SPACE.sub("\n", text)
