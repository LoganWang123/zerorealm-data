"""Tests for organic sprint phase 1 (no live WeChat / Zhihu / LLM)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from growth.combat_pack import CAMPAIGN, TOOL_PAGE_URL
from growth.organic_sprint_phase1 import (
    IMAGE_STATUS,
    KEYWORD_FUPAN,
    OPS_DATE,
    WECHAT_AUTOREPLY_PIECE_ID,
    WECHAT_TIEKU_DATE,
    WECHAT_TIEKU_PIECE_ID,
    WECHAT_TIEKU_TITLE,
    ZHIHU_DATE,
    ZHIHU_SCENARIO_PIECE_ID,
    ZHIHU_TITLE,
    build_organic_experiment_ledger_update,
    build_organic_only_schedule,
    build_phase1_manifest,
    build_wechat_autoreply_packet,
    build_wechat_tieku_packet,
    build_zhihu_scenario_packet,
    validate_autoreply_packet,
    validate_schedule,
    validate_wechat_tieku_packet,
    validate_zhihu_packet,
)
from growth.wechat_stockout_draft import (
    assert_html_visible_text_chinese_only,
    latin_tokens,
    visible_text_from_html,
)

ROOT = Path(__file__).resolve().parents[1]
LATIN_RE = re.compile(r"[A-Za-z]")


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_wechat_tieku_packet_chinese_only_single_cta_exact_date():
    md = (
        ROOT
        / "content/organic_packets/2026-08-15/o1-wechat-stockout-tieku.md"
    ).read_text(encoding="utf-8")
    packet = build_wechat_tieku_packet(body_markdown=md)
    validate_wechat_tieku_packet(packet)
    assert packet["title"] == WECHAT_TIEKU_TITLE
    assert packet["schedule_intent"]["publish_date"] == WECHAT_TIEKU_DATE
    assert packet["cta"]["url"].startswith(TOOL_PAGE_URL)
    assert f"utm_campaign={CAMPAIGN}" in packet["cta"]["url"]
    assert "utm_content=stockout_7steps_tieku" in packet["cta"]["url"]
    assert packet["image_status"] == IMAGE_STATUS
    assert latin_tokens(packet["visible_caption_zh"]) == []
    assert_html_visible_text_chinese_only(packet["html_caption"])
    assert "http" not in visible_text_from_html(packet["html_caption"]).lower()
    assert packet["cta"]["url"] in packet["html_caption"]
    assert packet["html_caption"].count(packet["cta"]["url"]) == 1
    forbidden = packet["schedule_intent"]["forbidden_surfaces"]
    assert "朋友圈" in forbidden
    assert packet["compliance"]["no_friends_circle"] is True
    assert packet["compliance"]["no_groups"] is True
    assert packet["compliance"]["no_personal_private_distribution"] is True
    assert len(packet["image_briefs"]) == 5
    assert packet["platform_formatting"]["panel_count"] == 4
    assert packet["platform_formatting"]["image_brief_count"] == 5
    assert packet["platform_formatting"]["panel_step_groups"] == [
        "1-2",
        "3-4",
        "5-6",
        "7",
    ]
    assert packet["image_briefs"][0]["purpose"] == "cover"
    assert packet["image_briefs"][0]["aspect_ratio"] == "1:1"
    assert [b["purpose"] for b in packet["image_briefs"][1:]] == [
        "tieku_panel",
        "tieku_panel",
        "tieku_panel",
        "tieku_panel",
    ]
    assert [b["aspect_ratio"] for b in packet["image_briefs"][1:]] == [
        "4:5",
        "4:5",
        "4:5",
        "4:5",
    ]
    for brief in packet["image_briefs"]:
        overlay = brief["text_overlay"]
        for key in ("primary", "secondary", "privacy_note"):
            assert latin_tokens(overlay[key]) == []
        assert brief["status"] == IMAGE_STATUS


def test_zhihu_scenario_packet_exact_date_single_cta_no_raw_url_line():
    template = (
        ROOT
        / "content/organic_packets/2026-08-15/o1-zhihu-inventory-stockout.md"
    ).read_text(encoding="utf-8")
    seed = build_zhihu_scenario_packet(body_markdown=template)
    body = template.replace("CTA_URL_PLACEHOLDER", seed["cta"]["url"])
    packet = build_zhihu_scenario_packet(body_markdown=body)
    validate_zhihu_packet(packet)
    assert packet["title"] == ZHIHU_TITLE
    assert packet["schedule_intent"]["publish_date"] == ZHIHU_DATE
    assert packet["body_markdown"].count(packet["cta"]["url"]) == 1
    assert f"utm_content=inventory_vs_stockout_qa" in packet["cta"]["url"]
    for line in packet["body_markdown"].splitlines():
        assert not line.strip().startswith("https://")
        assert not line.strip().startswith("http://")


def test_autoreply_keyword_fupan_no_excel_claim_chinese_only():
    packet = build_wechat_autoreply_packet()
    validate_autoreply_packet(packet)
    assert packet["piece_id"] == WECHAT_AUTOREPLY_PIECE_ID
    assert [k["keyword"] for k in packet["keyword_replies"]] == [KEYWORD_FUPAN]
    welcome = packet["welcome_reply"]
    keyword = packet["keyword_replies"][0]
    for text in (welcome["visible_text_zh"], keyword["visible_text_zh"]):
        assert LATIN_RE.search(text) is None
        assert "excel" not in text.lower()
        assert "xls" not in text.lower()
    assert "不是表格文件" in keyword["visible_text_zh"]
    assert packet["false_claim_guardrails"]["excel_download"] is False
    assert welcome["cta"]["url"].startswith(TOOL_PAGE_URL)
    assert keyword["cta"]["url"].startswith(TOOL_PAGE_URL)
    assert welcome["cta"]["url"] != keyword["cta"]["url"]
    assert "utm_content=wechat_welcome" in welcome["cta"]["url"]
    assert "utm_content=wechat_kw_fupanbiao" in keyword["cta"]["url"]


def test_organic_only_schedule_and_ledger_forbid_private_distribution():
    wechat = build_wechat_tieku_packet(body_markdown="# x\n")
    zhihu = build_zhihu_scenario_packet(
        body_markdown=(
            f"# t\n\n[打开智能柜周复盘工具页]("
            f"{TOOL_PAGE_URL}?utm_source=zhihu&utm_medium=article"
            f"&utm_campaign={CAMPAIGN}&utm_content=inventory_vs_stockout_qa)\n"
        )
    )
    autoreply = build_wechat_autoreply_packet()
    schedule = build_organic_only_schedule(
        wechat_packet=wechat,
        zhihu_packet=zhihu,
        autoreply_packet=autoreply,
    )
    validate_schedule(schedule)
    assert schedule["approved"] is True
    assert schedule["distribution_policy"]["friends_circle"] is False
    assert schedule["distribution_policy"]["groups"] is False
    assert schedule["distribution_policy"]["personal_private"] is False
    dates = {row["date"]: row["piece_id"] for row in schedule["calendar"]}
    assert dates[WECHAT_TIEKU_DATE] == WECHAT_TIEKU_PIECE_ID
    assert dates[ZHIHU_DATE] == ZHIHU_SCENARIO_PIECE_ID

    ledger = build_organic_experiment_ledger_update()
    assert ledger["organic_only"] is True
    assert ledger["distribution_policy"]["friends_circle"] is False
    assert "organic sprint phase 1" in ledger["notes"]


def test_committed_artifacts_match_phase1_contract():
    manifest = _load("data/growth/organic-sprint-phase1-manifest-2026-08-15.json")
    schedule = _load("data/growth/organic-only-schedule-2026-08-15.json")
    ledger = _load("data/growth/organic-experiment-ledger-2026-08-15.json")
    wechat = _load(
        "data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json"
    )
    zhihu = _load(
        "data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json"
    )
    autoreply = _load(
        "data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json"
    )

    assert manifest["ops_date"] == OPS_DATE
    assert manifest["sprint"] == "organic"
    assert manifest["status"] == "phase1_packets_ready"
    assert manifest["image_status"] == IMAGE_STATUS
    assert manifest["safety"]["external_wechat_zhihu_mutation"] is False
    assert manifest["safety"]["llm_api"] is False
    assert manifest["safety"]["friends_circle"] is False
    assert manifest["safety"]["groups"] is False
    assert manifest["safety"]["personal_private_distribution"] is False

    validate_wechat_tieku_packet(wechat)
    validate_zhihu_packet(zhihu)
    validate_autoreply_packet(autoreply)
    validate_schedule(schedule)

    assert ledger["organic_only"] is True
    assert wechat["schedule_intent"]["publish_date"] == "2026-08-17"
    assert zhihu["schedule_intent"]["publish_date"] == "2026-08-18"
    assert wechat["title"] == "柜机缺货先查这7步"
    assert zhihu["title"] == "库存显示有货，为什么柜机还是缺货？"
    assert len(wechat["image_briefs"]) == 5
    assert wechat["platform_formatting"]["panel_step_groups"] == [
        "1-2",
        "3-4",
        "5-6",
        "7",
    ]
    assert len(zhihu["image_briefs"]) == 1
    assert zhihu["image_briefs"][0]["purpose"] == "cover"
    assert zhihu["image_briefs"][0]["text_overlay"]["primary"] == "库存有货 ≠ 柜机可买"
    wechat_entry = next(
        p for p in manifest["packets"] if p["piece_id"] == WECHAT_TIEKU_PIECE_ID
    )
    assert wechat_entry["image_brief_count"] == 5
    assert wechat_entry["panel_count"] == 4
    assert [k["keyword"] for k in autoreply["keyword_replies"]] == ["复盘表"]

    template = _load("data/growth/experiment-ledger.template.json")
    assert "organic sprint phase 1" in template["notes"]

    report = (
        ROOT / "docs/reports/organic-sprint-phase1-2026-08-15.md"
    ).read_text(encoding="utf-8")
    assert "awaiting_antigravity_images" in report
    assert "2026-08-17" in report
    assert "2026-08-18" in report


def test_manifest_builder_wires_tracking_and_handoff():
    wechat = build_wechat_tieku_packet(body_markdown="# a\n")
    zhihu = build_zhihu_scenario_packet(
        body_markdown=(
            f"[打开智能柜周复盘工具页]("
            f"{TOOL_PAGE_URL}?utm_source=zhihu&utm_medium=article"
            f"&utm_campaign={CAMPAIGN}&utm_content=inventory_vs_stockout_qa)\n"
        )
    )
    autoreply = build_wechat_autoreply_packet()
    schedule = build_organic_only_schedule(
        wechat_packet=wechat,
        zhihu_packet=zhihu,
        autoreply_packet=autoreply,
    )
    manifest = build_phase1_manifest(
        wechat_packet=wechat,
        zhihu_packet=zhihu,
        autoreply_packet=autoreply,
        schedule=schedule,
        article_source_paths={
            WECHAT_TIEKU_PIECE_ID: "a.md",
            ZHIHU_SCENARIO_PIECE_ID: "b.md",
            WECHAT_AUTOREPLY_PIECE_ID: "c.md",
        },
    )
    assert len(manifest["packets"]) == 3
    assert manifest["continue_stop_metrics"]["continue_all_of"]
    assert manifest["browser_handoff"]["phase1_mutates_external_state"] is False
    assert manifest["tracking_ids"]["campaign"] == CAMPAIGN
