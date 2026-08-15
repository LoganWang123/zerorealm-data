"""Tests for organic sprint phase 1 (no live WeChat / Zhihu / LLM)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image

from growth.combat_pack import CAMPAIGN, TOOL_PAGE_URL
from growth.organic_sprint_phase1 import (
    IMAGE_STATUS,
    KEYWORD_FUPAN,
    OPS_DATE,
    POINT_CONTRIBUTION_PIECE_ID,
    POINT_CONTRIBUTION_TITLE,
    STATUS_ASSETS_READY,
    STATUS_BLOCKED,
    STATUS_CANCELED,
    STATUS_CONFIGURED,
    STATUS_DELETED,
    STATUS_DRAFT_SAVED,
    STATUS_PUBLISHED,
    STATUS_REVISION_PENDING,
    STATUS_SCHEDULED,
    WECHAT_AUTOREPLY_PIECE_ID,
    WECHAT_BLOCK_REASON,
    WECHAT_KEYWORD_RULE_ID,
    WECHAT_TIEKU_APP_ID,
    WECHAT_TIEKU_CANCEL_REASON,
    WECHAT_TIEKU_DATA_SEQ,
    WECHAT_TIEKU_DATE,
    WECHAT_TIEKU_PIECE_ID,
    WECHAT_TIEKU_TITLE,
    WECHAT_WELCOME_RULE_ID,
    ZHIHU_CTA_LEAD_IN_ZH,
    ZHIHU_DATE,
    ZHIHU_DRAFT_ID,
    ZHIHU_PLANNED_WINDOW,
    ZHIHU_REVISION_REASON,
    ZHIHU_SCENARIO_PIECE_ID,
    ZHIHU_TITLE,
    assert_deleted_only_for_legacy_interview_cta,
    assert_revision_pending_not_publishable,
    build_external_ops_verification,
    build_organic_experiment_ledger_update,
    build_organic_only_schedule,
    build_phase1_manifest,
    build_wechat_autoreply_packet,
    build_wechat_tieku_packet,
    build_zhihu_scenario_packet,
    validate_autoreply_packet,
    validate_external_ops,
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
IMAGES_READY = "images_ready"
WECHAT_ASSET_DIR = (
    ROOT / "assets/generated/organic-sprint/2026-08-15/o1-wechat-stockout-tieku"
)
WECHAT_EXPECTED = [
    {
        "filename": "cover.png",
        "purpose": "cover",
        "aspect_ratio": "1:1",
        "width": 1080,
        "height": 1080,
        "sha256": "ae31a77638a5489a139cce7614f0962be784a23be428435738bff19c7584b463",
        "asset_key": "cover",
    },
    {
        "filename": "panel-1.png",
        "purpose": "tieku_panel",
        "aspect_ratio": "4:5",
        "width": 1080,
        "height": 1350,
        "sha256": "132511863077f3ff8a4147ab14534e2315ad12963a6f90e2b1c797351a66343c",
        "asset_key": "panel_1",
    },
    {
        "filename": "panel-2.png",
        "purpose": "tieku_panel",
        "aspect_ratio": "4:5",
        "width": 1080,
        "height": 1350,
        "sha256": "7289d78f42087818959219a1afc085a83e12ba369bd65d1fc0cff83cdb00b436",
        "asset_key": "panel_2",
    },
    {
        "filename": "panel-3.png",
        "purpose": "tieku_panel",
        "aspect_ratio": "4:5",
        "width": 1080,
        "height": 1350,
        "sha256": "6caed6695b90132e0a8178be9e777c5c087f33ab3c536b5a076e37a17ea769db",
        "asset_key": "panel_3",
    },
    {
        "filename": "panel-4.png",
        "purpose": "tieku_panel",
        "aspect_ratio": "4:5",
        "width": 1080,
        "height": 1350,
        "sha256": "bf4fa4b68bd76ff07413c8708c30c485408228a6240e600564815a90a92b80a2",
        "asset_key": "panel_4",
    },
]


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
    assert manifest["status"] == "phase1_external_ops_recorded"
    assert manifest["image_status"] == IMAGES_READY
    assert manifest["safety"]["external_wechat_zhihu_mutation"] is False
    assert manifest["safety"]["browser_manual_ops"] is True
    assert manifest["safety"]["cdn_urls_recorded"] is False
    assert manifest["safety"]["tokens_recorded"] is False
    assert manifest["safety"]["cookies_recorded"] is False
    assert manifest["safety"]["llm_api"] is False
    assert manifest["safety"]["friends_circle"] is False
    assert manifest["safety"]["groups"] is False
    assert manifest["safety"]["personal_private_distribution"] is False

    validate_wechat_tieku_packet(wechat)
    validate_zhihu_packet(zhihu)
    validate_autoreply_packet(autoreply)
    validate_schedule(schedule)
    validate_external_ops(manifest["external_ops"])
    validate_external_ops(ledger["organic_phase1"]["external_ops"])

    assert ledger["organic_only"] is True
    assert wechat["schedule_intent"]["publish_date"] == "2026-08-17"
    assert zhihu["schedule_intent"]["publish_date"] == "2026-08-18"
    assert wechat["title"] == "柜机缺货先查这7步"
    assert zhihu["title"] == "库存显示有货，为什么柜机还是缺货？"
    assert wechat["image_status"] == IMAGES_READY
    assert zhihu["image_status"] == IMAGES_READY
    assert wechat["external_status"] == STATUS_CANCELED
    assert wechat["cancel_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert wechat["draft_status"] == STATUS_DRAFT_SAVED
    assert wechat["employment_boundary_synced"] is True
    assert wechat["publish_blocked"] is True
    assert wechat["block_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert wechat["scheduled"] is False
    assert wechat["published"] is False
    assert wechat["external_draft_deleted"] is False
    assert wechat["provenance_retained"] is True
    assert zhihu["external_status"] == STATUS_DRAFT_SAVED
    assert zhihu["employment_boundary_synced"] is True
    assert zhihu["publish_blocked"] is False
    assert zhihu.get("revision_pending") is False
    assert zhihu.get("block_reason") in (None, "")
    assert zhihu["local_packet_corrected"] is True
    assert zhihu["legacy_interview_cta_status"] == STATUS_DELETED
    assert zhihu["scheduled"] is False
    assert zhihu["published"] is False
    assert autoreply["external_status"] == STATUS_CONFIGURED
    assert autoreply["employment_boundary_synced"] is True
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
    zhihu_entry = next(
        p for p in manifest["packets"] if p["piece_id"] == ZHIHU_SCENARIO_PIECE_ID
    )
    autoreply_entry = next(
        p for p in manifest["packets"] if p["piece_id"] == WECHAT_AUTOREPLY_PIECE_ID
    )
    assert wechat_entry["image_status"] == IMAGES_READY
    assert zhihu_entry["image_status"] == IMAGES_READY
    assert wechat_entry["external_status"] == STATUS_CANCELED
    assert wechat_entry["draft_status"] == STATUS_DRAFT_SAVED
    assert wechat_entry["assets_status"] == STATUS_ASSETS_READY
    assert wechat_entry["employment_boundary_synced"] is True
    assert wechat_entry["publish_blocked"] is True
    assert wechat_entry["block_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert wechat_entry["scheduled"] is False
    assert wechat_entry["published"] is False
    assert wechat_entry["app_id"] == WECHAT_TIEKU_APP_ID
    assert wechat_entry["data_seq"] == WECHAT_TIEKU_DATA_SEQ
    assert zhihu_entry["external_status"] == STATUS_DRAFT_SAVED
    assert zhihu_entry["employment_boundary_synced"] is True
    assert zhihu_entry["publish_blocked"] is False
    assert zhihu_entry["revision_pending"] is False
    assert zhihu_entry["legacy_interview_cta_status"] == STATUS_DELETED
    assert zhihu_entry["draft_id"] == ZHIHU_DRAFT_ID
    assert zhihu_entry["planned_publish_window"] == ZHIHU_PLANNED_WINDOW
    assert zhihu_entry["scheduled"] is False
    assert zhihu_entry["published"] is False
    assert autoreply_entry["external_status"] == STATUS_CONFIGURED
    assert autoreply_entry["employment_boundary_synced"] is True
    assert autoreply_entry["welcome_rule_id"] == WECHAT_WELCOME_RULE_ID
    assert autoreply_entry["keyword_rule_id"] == WECHAT_KEYWORD_RULE_ID
    assert wechat_entry["image_brief_count"] == 5
    assert wechat_entry["panel_count"] == 4
    assert [k["keyword"] for k in autoreply["keyword_replies"]] == ["复盘表"]

    template = _load("data/growth/experiment-ledger.template.json")
    assert "organic sprint phase 1" in template["notes"]
    assert STATUS_SCHEDULED not in (
        wechat_entry["external_status"],
        zhihu_entry["external_status"],
        autoreply_entry["external_status"],
    )
    assert STATUS_PUBLISHED not in (
        wechat_entry["external_status"],
        zhihu_entry["external_status"],
        autoreply_entry["external_status"],
    )
    assert STATUS_DELETED not in (
        wechat_entry["external_status"],
        zhihu_entry["external_status"],
        autoreply_entry["external_status"],
        wechat_entry["draft_status"],
    )

    report = (
        ROOT / "docs/reports/organic-sprint-phase1-2026-08-15.md"
    ).read_text(encoding="utf-8")
    assert IMAGES_READY in report
    assert "2026-08-17" in report
    assert "2026-08-18" in report
    assert STATUS_CONFIGURED in report
    assert STATUS_DRAFT_SAVED in report
    assert STATUS_CANCELED in report
    assert WECHAT_TIEKU_CANCEL_REASON in report
    assert POINT_CONTRIBUTION_TITLE in report or "单点贡献" in report or "production_ready_revision" in report
    assert "legacy_interview_cta_status" in report
    assert STATUS_DELETED in report
    assert "resolved" in report.lower()
    assert ZHIHU_REVISION_REASON in report
    assert "employment_boundary_synced" in report
    assert ZHIHU_CTA_LEAD_IN_ZH in report
    assert "cdn" not in report.lower() or "no CDN" in report
    assert "cookie" not in report.lower() or "cookies recorded" in report.lower()
    assert "约 58" not in report
    assert "58 分钟" not in report
    assert "@gmail" not in report.lower()


def test_external_ops_lifecycle_distinguishes_draft_from_scheduled_published():
    ops = build_external_ops_verification()
    validate_external_ops(ops)
    assert_deleted_only_for_legacy_interview_cta(ops)
    assert ops["privacy"]["cdn_urls_recorded"] is False
    assert ops["privacy"]["login_tokens_recorded"] is False
    assert ops["privacy"]["cookies_recorded"] is False
    assert ops["privacy"]["antigravity_account_recorded"] is False
    assert ops["privacy"]["antigravity_email_recorded"] is False
    assert ops["privacy"]["quota_recovery_clock_recorded"] is False
    assert ops["truthfulness_correction"]["external_wechat_deleted"] is False
    assert ops["truthfulness_correction"]["external_zhihu_revision_pending"] is False

    autoreply = ops["pieces"][WECHAT_AUTOREPLY_PIECE_ID]
    wechat = ops["pieces"][WECHAT_TIEKU_PIECE_ID]
    zhihu = ops["pieces"][ZHIHU_SCENARIO_PIECE_ID]

    assert autoreply["status"] == STATUS_CONFIGURED
    assert autoreply["employment_boundary_synced"] is True
    assert autoreply["welcome"]["rule_id"] == WECHAT_WELCOME_RULE_ID
    assert autoreply["keyword"]["rule_id"] == WECHAT_KEYWORD_RULE_ID
    assert autoreply["keyword"]["match"] == "exact"
    assert autoreply["welcome"]["enabled"] is True
    assert autoreply["keyword"]["enabled"] is True
    assert autoreply["welcome"]["status"] == STATUS_CONFIGURED
    assert autoreply["keyword"]["status"] == STATUS_CONFIGURED

    assert wechat["status"] == STATUS_CANCELED
    assert wechat["cancel_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert wechat["draft_status"] == STATUS_DRAFT_SAVED
    assert wechat["employment_boundary_synced"] is True
    assert wechat["publish_blocked"] is True
    assert wechat["block_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert wechat["assets_status"] == STATUS_ASSETS_READY
    assert wechat["scheduled"] is False
    assert wechat["published"] is False
    assert wechat["external_draft_deleted"] is False
    assert wechat["provenance_retained"] is True
    assert wechat["status"] not in (STATUS_SCHEDULED, STATUS_PUBLISHED, STATUS_DELETED)
    assert wechat["schedule_attempt"]["cancel_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert wechat["schedule_attempt"]["prior_block_reason"] == WECHAT_BLOCK_REASON
    assert wechat["schedule_attempt"]["exited_safely"] is True
    assert wechat["app_id"] == WECHAT_TIEKU_APP_ID
    assert wechat["data_seq"] == WECHAT_TIEKU_DATA_SEQ
    assert wechat["image_count"] == 5
    assert ops["blockers"] == []
    assert ops["canceled_plans"][0]["reason"] == WECHAT_TIEKU_CANCEL_REASON

    assert zhihu["status"] == STATUS_DRAFT_SAVED
    assert zhihu["revision_pending"] is False
    assert zhihu["employment_boundary_synced"] is True
    assert zhihu["publish_blocked"] is False
    assert zhihu["block_reason"] is None
    assert zhihu["local_packet_corrected"] is True
    assert zhihu["external_draft_accepted"] is True
    assert zhihu["legacy_interview_cta_status"] == STATUS_DELETED
    assert zhihu["cta_verification"]["lead_in_zh"] == ZHIHU_CTA_LEAD_IN_ZH
    assert zhihu["scheduled"] is False
    assert zhihu["published"] is False
    assert zhihu["status"] not in (
        STATUS_SCHEDULED,
        STATUS_PUBLISHED,
        STATUS_REVISION_PENDING,
    )
    assert zhihu["draft_id"] == ZHIHU_DRAFT_ID
    assert zhihu["planned_publish_window"] == ZHIHU_PLANNED_WINDOW
    assert ops["blockers"] == []
    assert ops["canceled_plans"][0]["reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert all(e["resolved"] is True for e in ops["resolved_events"])
    assert any(
        e["id"] == "zhihu_revision_pending_quota" and e["reason"] == ZHIHU_REVISION_REASON
        for e in ops["resolved_events"]
    )
    assert any(
        e["id"] == "wechat_tieku_schedule_canceled_topic_overlap"
        and e["reason"] == WECHAT_TIEKU_CANCEL_REASON
        for e in ops["resolved_events"]
    )

    ledger = build_organic_experiment_ledger_update()
    assert ledger["alerts"][0]["reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert ledger["alerts"][0]["resolved"] is True
    quota_alert = next(a for a in ledger["alerts"] if a["id"] == "zhihu_revision_pending_quota")
    assert quota_alert["resolved"] is True
    assert "employment_boundary_synced" in ledger["notes"]
    assert "antigravity_quota_temporarily_exhausted" in ledger["notes"]
    assert "resolved" in ledger["notes"]
    assert STATUS_CONFIGURED in ledger["notes"] or "configured" in ledger["notes"]
    assert STATUS_CANCELED in ledger["notes"] or "canceled" in ledger["notes"]
    assert WECHAT_TIEKU_CANCEL_REASON in ledger["notes"]


def test_revision_pending_must_not_be_scheduled_or_published():
    synthetic = {
        "status": STATUS_REVISION_PENDING,
        "publish_blocked": True,
        "scheduled": False,
        "published": False,
        "publish_status": "not_published",
        "schedule_status": "unsupported_on_web",
    }
    assert_revision_pending_not_publishable(synthetic)

    bad_scheduled = dict(synthetic, scheduled=True)
    try:
        assert_revision_pending_not_publishable(bad_scheduled)
        raise AssertionError("expected scheduled revision_pending to fail")
    except ValueError as exc:
        assert "scheduled/published" in str(exc)

    bad_published = dict(synthetic, published=True)
    try:
        assert_revision_pending_not_publishable(bad_published)
        raise AssertionError("expected published revision_pending to fail")
    except ValueError as exc:
        assert "scheduled/published" in str(exc)

    bad_unblocked = dict(synthetic, publish_blocked=False)
    try:
        assert_revision_pending_not_publishable(bad_unblocked)
        raise AssertionError("expected publish_blocked=false to fail")
    except ValueError as exc:
        assert "publish_blocked" in str(exc)

    ops = build_external_ops_verification()
    schedule = _load("data/growth/organic-only-schedule-2026-08-15.json")
    zhihu_row = next(
        row
        for row in schedule["calendar"]
        if row["piece_id"] == ZHIHU_SCENARIO_PIECE_ID
    )
    assert zhihu_row["status"] == STATUS_DRAFT_SAVED
    assert zhihu_row["publish_blocked"] is False
    assert zhihu_row["revision_pending"] is False
    assert zhihu_row["scheduled"] is False
    assert zhihu_row["published"] is False
    assert zhihu_row["status"] not in (STATUS_SCHEDULED, STATUS_PUBLISHED)

    # Mutating committed calendar to scheduled/published must fail validation.
    poisoned = json.loads(json.dumps(schedule))
    poisoned_row = next(
        row
        for row in poisoned["calendar"]
        if row["piece_id"] == ZHIHU_SCENARIO_PIECE_ID
    )
    poisoned_row["status"] = STATUS_SCHEDULED
    poisoned_row["scheduled"] = True
    try:
        validate_schedule(poisoned)
        raise AssertionError("scheduled Zhihu calendar must be rejected")
    except ValueError as exc:
        assert "scheduled/published" in str(exc) or "draft_saved" in str(exc)

    poisoned_row["status"] = STATUS_PUBLISHED
    poisoned_row["scheduled"] = False
    poisoned_row["published"] = True
    try:
        validate_schedule(poisoned)
        raise AssertionError("published Zhihu calendar must be rejected")
    except ValueError as exc:
        assert "scheduled/published" in str(exc) or "draft_saved" in str(exc)

    ops_poisoned = json.loads(json.dumps(ops))
    ops_poisoned["pieces"][ZHIHU_SCENARIO_PIECE_ID]["status"] = STATUS_PUBLISHED
    ops_poisoned["pieces"][ZHIHU_SCENARIO_PIECE_ID]["published"] = True
    try:
        validate_external_ops(ops_poisoned)
        raise AssertionError("published Zhihu must be rejected by external_ops")
    except ValueError:
        pass

    deleted_poison = json.loads(json.dumps(ops))
    deleted_poison["pieces"][WECHAT_AUTOREPLY_PIECE_ID]["status"] = STATUS_DELETED
    try:
        validate_external_ops(deleted_poison)
        raise AssertionError("deleted autoreply must be rejected")
    except ValueError as exc:
        assert "deleted" in str(exc).lower() or "configured" in str(exc)

    blob = json.dumps(ops, ensure_ascii=False).lower()
    assert "@gmail" not in blob
    assert "分钟后恢复" not in blob
    assert "58 分钟" not in blob
    assert "quota recovers" not in blob


def test_wechat_tieku_committed_assets_match_provenance_and_chinese_overlays():
    wechat = _load(
        "data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json"
    )
    manifest = _load("data/growth/organic-sprint-phase1-manifest-2026-08-15.json")
    provenance = _load("assets/generated/organic-sprint/2026-08-15/provenance.json")
    provenance_mirror = _load(
        "data/growth/organic-sprint-phase1-image-provenance-2026-08-15.json"
    )
    assert provenance == provenance_mirror
    assert provenance["generator_agent"] == "antigravity"
    assert provenance["model"] == "gemini-3.7-flash-high"
    assert provenance["status"] == IMAGES_READY

    wechat_entry = next(
        p for p in manifest["packets"] if p["piece_id"] == WECHAT_TIEKU_PIECE_ID
    )
    zhihu_entry = next(
        p for p in manifest["packets"] if p["piece_id"] == ZHIHU_SCENARIO_PIECE_ID
    )
    assert wechat["image_status"] == IMAGES_READY
    assert wechat_entry["image_status"] == IMAGES_READY
    assert zhihu_entry["image_status"] == IMAGES_READY
    assert manifest["image_status"] == IMAGES_READY
    assert len(wechat["image_briefs"]) == 5

    wechat_prov = [
        img
        for img in provenance["images"]
        if img["piece_id"] == WECHAT_TIEKU_PIECE_ID
    ]
    assert len(wechat_prov) == 5
    assert any(
        img["piece_id"] == ZHIHU_SCENARIO_PIECE_ID for img in provenance["images"]
    )

    for brief, expected, prov in zip(
        wechat["image_briefs"], WECHAT_EXPECTED, wechat_prov, strict=True
    ):
        rel = (
            "assets/generated/organic-sprint/2026-08-15/"
            f"o1-wechat-stockout-tieku/{expected['filename']}"
        )
        path = WECHAT_ASSET_DIR / expected["filename"]
        assert path.is_file()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with Image.open(path) as image:
            width, height = image.size
        assert digest == expected["sha256"]
        assert (width, height) == (expected["width"], expected["height"])
        assert brief["status"] == IMAGES_READY
        assert brief["purpose"] == expected["purpose"]
        assert brief["aspect_ratio"] == expected["aspect_ratio"]
        assert brief["asset_path"] == rel
        assert brief["sha256"] == expected["sha256"]
        assert brief["width"] == expected["width"]
        assert brief["height"] == expected["height"]
        assert brief["model"] == "gemini-3.7-flash-high"
        assert brief["review_result"] == "PASS"
        assert wechat_entry["assets"][expected["asset_key"]] == rel
        assert prov["asset_path"] == rel
        assert prov["sha256"] == expected["sha256"]
        assert prov["dimensions"] == {
            "width": expected["width"],
            "height": expected["height"],
        }
        assert prov["file_size_bytes"] == path.stat().st_size
        assert prov["visual_inspection"]["result"] == "PASS"
        assert prov["visual_inspection"]["reviewer"] == "antigravity"
        overlay = brief["text_overlay"]
        for key in ("primary", "secondary", "privacy_note"):
            assert latin_tokens(overlay[key]) == []

    assert latin_tokens(wechat["visible_caption_zh"]) == []
    assert_html_visible_text_chinese_only(wechat["html_caption"])
    validate_wechat_tieku_packet(wechat)


def test_forbidden_cta_terms_and_professional_boundaries():
    from growth.organic_sprint_phase1 import (
        FORBIDDEN_CTA_TERMS,
        PROFESSIONAL_BOUNDARIES_ZH,
        assert_no_forbidden_cta_terms,
        assert_professional_boundaries_declared,
        build_wechat_autoreply_packet,
        build_wechat_tieku_packet,
        build_zhihu_scenario_packet,
    )

    wechat = build_wechat_tieku_packet(body_markdown="# x\n")
    zhihu = build_zhihu_scenario_packet(
        body_markdown=(
            f"[打开智能柜周复盘工具页]("
            f"{TOOL_PAGE_URL}?utm_source=zhihu&utm_medium=article"
            f"&utm_campaign={CAMPAIGN}&utm_content=inventory_vs_stockout_qa)\n"
        )
    )
    autoreply = build_wechat_autoreply_packet()

    for packet in (wechat, zhihu, autoreply):
        assert_professional_boundaries_declared(packet["compliance"])
        assert packet["compliance"]["conversion_funnel"]
        assert "内部经营数据" in packet["compliance"]["professional_boundaries_zh"]

    blobs = [
        wechat["visible_caption_zh"],
        wechat["cta"]["copy"],
        wechat["body_markdown"],
        zhihu["body_markdown"],
        zhihu["cta"]["copy"],
        autoreply["welcome_reply"]["visible_text_zh"],
        autoreply["keyword_replies"][0]["visible_text_zh"],
    ]
    for blob in blobs:
        assert_no_forbidden_cta_terms(blob)
        for term in FORBIDDEN_CTA_TERMS:
            assert term not in blob

    ledger = build_organic_experiment_ledger_update()
    assert "interview_click" not in ledger["funnel_manual"]
    assert "keyword_replies" in ledger["funnel_manual"]
    assert ledger["funnel_manual"]["keyword_replies"] == 0
    assert ledger["anonymous_metrics"]["content_prep_on_time_rate"] is None
    targets = ledger["experiment_targets"]
    assert "keyword_replies" in targets
    assert "交流线索" not in json.dumps(targets, ensure_ascii=False)
    assert PROFESSIONAL_BOUNDARIES_ZH in ledger["notes"]

    committed = [
        ROOT / "data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json",
        ROOT / "data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json",
        ROOT / "data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json",
        ROOT / "content/organic_packets/2026-08-15/o1-wechat-stockout-tieku.md",
        ROOT / "content/organic_packets/2026-08-15/o1-zhihu-inventory-stockout.md",
        ROOT / "content/organic_packets/2026-08-15/o1-wechat-autoreply-fupan.md",
    ]
    for path in committed:
        text = path.read_text(encoding="utf-8")
        for term in (
            "预约运营商访谈",
            "有效运营商交流线索",
            "交流线索",
            "加微信",
            "一对一联系",
        ):
            assert term not in text, f"{term} found in {path}"


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
    assert len(manifest["packets"]) == 4
    assert manifest["continue_stop_metrics"]["continue_all_of"]
    assert manifest["browser_handoff"]["phase1_mutates_external_state"] is False
    assert manifest["browser_handoff"]["browser_manual_ops_recorded"] is True
    assert manifest["status"] == "phase1_external_ops_recorded"
    assert manifest["tracking_ids"]["campaign"] == CAMPAIGN
    assert manifest["packets"][0]["external_status"] == STATUS_CANCELED
    assert manifest["packets"][1]["external_status"] == "production_ready_revision"
    assert manifest["packets"][1]["external_sync_status"] == "external_sync_pending"
    assert manifest["packets"][2]["external_status"] == STATUS_DRAFT_SAVED
    assert manifest["packets"][3]["external_status"] == STATUS_CONFIGURED
    assert manifest["packets"][0]["employment_boundary_synced"] is True
    assert manifest["packets"][2]["employment_boundary_synced"] is True
    assert manifest["packets"][2]["publish_blocked"] is False
    assert manifest["packets"][2]["revision_pending"] is False
    assert manifest["packets"][2]["legacy_interview_cta_status"] == STATUS_DELETED
    assert manifest["packets"][3]["employment_boundary_synced"] is True
    validate_external_ops(manifest["external_ops"])
    by_piece = {row["piece_id"]: row for row in schedule["calendar"]}
    assert by_piece[WECHAT_AUTOREPLY_PIECE_ID]["status"] == STATUS_CONFIGURED
    assert by_piece[WECHAT_TIEKU_PIECE_ID]["status"] == STATUS_CANCELED
    assert by_piece[WECHAT_TIEKU_PIECE_ID]["draft_status"] == STATUS_DRAFT_SAVED
    assert by_piece[WECHAT_TIEKU_PIECE_ID]["cancel_reason"] == WECHAT_TIEKU_CANCEL_REASON
    assert by_piece[ZHIHU_SCENARIO_PIECE_ID]["status"] == STATUS_DRAFT_SAVED
    assert by_piece[WECHAT_TIEKU_PIECE_ID]["scheduled"] is False
    assert by_piece[ZHIHU_SCENARIO_PIECE_ID]["published"] is False
    assert by_piece[ZHIHU_SCENARIO_PIECE_ID]["publish_blocked"] is False
    assert by_piece[ZHIHU_SCENARIO_PIECE_ID]["block_reason"] is None
    assert by_piece[POINT_CONTRIBUTION_PIECE_ID]["status"] == "production_ready_revision"
    assert by_piece[POINT_CONTRIBUTION_PIECE_ID]["external_sync_status"] == (
        "external_sync_pending"
    )
    assert schedule["anti_duplication"]["cancel_reason_code"] == WECHAT_TIEKU_CANCEL_REASON
    assert manifest["browser_handoff"]["remaining_blockers"] == []
    assert manifest["browser_handoff"]["canceled_plans"][0]["reason"] == (
        WECHAT_TIEKU_CANCEL_REASON
    )