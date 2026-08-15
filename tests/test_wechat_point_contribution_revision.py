"""Tests for WeChat point-contribution production revision + draft sync acceptance."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from growth.wechat_point_contribution_revision import (
    AGY_ACCEPTANCE,
    AGY_MODEL,
    AGY_VERIFIED_AT,
    CANCEL_REASON_TOPIC_OVERLAP,
    CORE_QUESTION,
    CORE_QUESTION_TAGS,
    CTA_EXACT,
    DIGEST,
    EXTERNAL_APP_ID,
    EXTERNAL_DATA_SEQ,
    EXTERNAL_DATA_SEQ_PREVIOUS,
    PIECE_ID,
    STATUS_DRAFT_SAVED,
    STATUS_EXTERNAL_SYNC_COMPLETED,
    STATUS_PRODUCTION_READY_REVISION,
    TITLE,
    assert_draft_synced_not_published,
    assert_no_privacy_secrets_in_blob,
    assert_no_same_channel_core_question_overlap,
    assert_not_marked_synced_or_published,
    build_revision_packet,
    same_channel_core_question_blocked,
)
from growth.wechat_stockout_draft import visible_text_from_html

ROOT = Path(__file__).resolve().parents[1]
LATIN_RE = re.compile(r"[A-Za-z]")


def test_revision_packet_status_and_external_ids():
    packet = build_revision_packet()
    assert packet["title"] == TITLE
    assert packet["status"] == STATUS_PRODUCTION_READY_REVISION
    assert packet["external_sync_status"] == STATUS_EXTERNAL_SYNC_COMPLETED
    assert packet["draft_status"] == STATUS_DRAFT_SAVED
    assert packet["scheduled"] is False
    assert packet["published"] is False
    assert packet["synced"] is True
    assert packet["auto_publish"] is False
    assert packet["compliance"]["auto_publish"] is False
    assert packet["external_draft"]["app_id"] == EXTERNAL_APP_ID
    assert packet["external_draft"]["data_seq"] == EXTERNAL_DATA_SEQ
    assert packet["external_draft"]["data_seq_previous"] == EXTERNAL_DATA_SEQ_PREVIOUS
    assert packet["external_draft"]["updated_at"] == AGY_VERIFIED_AT
    assert packet["agy_acceptance"]["model"] == AGY_MODEL
    assert packet["agy_acceptance"]["result"] == AGY_ACCEPTANCE
    assert packet["cta"]["copy"] == CTA_EXACT
    assert packet["digest"] == DIGEST
    assert LATIN_RE.search(packet["digest"]) is None
    assert_draft_synced_not_published(packet)
    assert_not_marked_synced_or_published(packet)
    assert_no_privacy_secrets_in_blob(packet)


def test_draft_sync_is_not_publish():
    packet = build_revision_packet()
    assert packet["synced"] is True
    assert packet["external_sync_status"] == STATUS_EXTERNAL_SYNC_COMPLETED
    assert packet["draft_status"] == STATUS_DRAFT_SAVED
    assert packet["scheduled"] is False
    assert packet["published"] is False
    assert packet["auto_publish"] is False
    bad = dict(packet)
    bad["published"] = True
    with pytest.raises(ValueError, match="scheduled/published"):
        assert_draft_synced_not_published(bad)
    bad2 = dict(packet)
    bad2["scheduled"] = True
    with pytest.raises(ValueError, match="scheduled/published"):
        assert_draft_synced_not_published(bad2)
    bad3 = dict(packet)
    bad3["auto_publish"] = True
    with pytest.raises(ValueError, match="auto_publish"):
        assert_draft_synced_not_published(bad3)


def test_privacy_fields_not_recorded():
    packet = build_revision_packet()
    privacy = packet["privacy"]
    for key in (
        "cdn_urls_recorded",
        "file_ids_recorded",
        "login_tokens_recorded",
        "cookies_recorded",
        "asset_addresses_recorded",
    ):
        assert privacy[key] is False
    blob = json.dumps(packet, ensure_ascii=False)
    assert "mmbiz.qpic.cn" not in blob
    assert re.search(r'"file_id"\s*:\s*"[^"]+"', blob) is None
    assert re.search(r'"login_token"\s*:\s*"[^"]+"', blob) is None
    assert re.search(r'"(cookie|cookies)"\s*:\s*"[^"]+"', blob, re.I) is None
    assert re.search(r'"asset_(url|address)"\s*:\s*"[^"]+"', blob) is None
    # Acceptance surface must not introduce secret value keys.
    poisoned = dict(packet)
    poisoned["file_id"] = "should-not-exist"
    with pytest.raises(ValueError, match="file_id"):
        assert_no_privacy_secrets_in_blob(poisoned)


def test_revision_visible_text_chinese_only_exact_cta():
    packet = build_revision_packet()
    visible = visible_text_from_html(packet["body_html"])
    assert LATIN_RE.search(visible) is None
    assert CTA_EXACT in visible
    assert visible.count(CTA_EXACT) == 1
    for bad in (
        "DyDo",
        "Fuji",
        "ZeroRealm",
        "SKU",
        "GMV",
        "IR",
        "Excel",
        "hi@zerorealm.tech",
        "https://",
        "下载表格",
        "访谈",
        "加微信",
        "一对一",
        "打开智能柜周复盘工具页",
    ):
        assert bad not in visible
        assert bad not in packet["digest"]
    assert "甲" in visible and "己" in visible
    assert "周单点贡献" in visible
    assert "两周" in visible
    assert "公开披露" in visible


def test_committed_revision_artifacts_match_builder():
    packet_path = (
        ROOT / f"data/growth/content-packet-{PIECE_ID}-2026-08-15.json"
    )
    handoff = ROOT / "docs/reports/wechat-point-contribution-revision-2026-08-15.md"
    agy = ROOT / f"data/growth/agy-sync-{PIECE_ID}-2026-08-15.json"
    html = ROOT / f"data/growth/evidence/2026-08-15/{PIECE_ID}/article.html"
    md = ROOT / f"content/organic_packets/2026-08-15/{PIECE_ID}.md"
    for path in (packet_path, handoff, agy, html, md):
        assert path.is_file(), path
    committed = json.loads(packet_path.read_text(encoding="utf-8"))
    built = build_revision_packet(body_md=md.read_text(encoding="utf-8"))
    assert committed["status"] == STATUS_PRODUCTION_READY_REVISION
    assert committed["external_sync_status"] == STATUS_EXTERNAL_SYNC_COMPLETED
    assert committed["draft_status"] == STATUS_DRAFT_SAVED
    assert committed["synced"] is True
    assert committed["scheduled"] is False
    assert committed["published"] is False
    assert committed["digest"] == built["digest"]
    assert committed["cta"]["copy"] == CTA_EXACT
    assert committed["external_draft"]["data_seq"] == EXTERNAL_DATA_SEQ
    assert committed["agy_acceptance"]["result"] == AGY_ACCEPTANCE
    assert_draft_synced_not_published(committed)
    assert_no_privacy_secrets_in_blob(committed)
    agy_payload = json.loads(agy.read_text(encoding="utf-8"))
    assert agy_payload["status"] == STATUS_PRODUCTION_READY_REVISION
    assert agy_payload["external_sync_status"] == STATUS_EXTERNAL_SYNC_COMPLETED
    assert agy_payload["synced"] is True
    assert agy_payload["published"] is False
    assert agy_payload["visible"]["cta"] == CTA_EXACT
    assert_no_privacy_secrets_in_blob(agy_payload)
    handoff_text = handoff.read_text(encoding="utf-8")
    assert "external_sync_completed" in handoff_text
    assert "PASS" in handoff_text
    assert AGY_MODEL in handoff_text
    assert EXTERNAL_APP_ID in handoff_text
    assert EXTERNAL_DATA_SEQ in handoff_text
    assert "file_id" not in handoff_text.lower() or "不记录" in handoff_text


def test_same_channel_14d_core_question_blocks_overlap():
    existing = [
        {
            "piece_id": PIECE_ID,
            "channel": "wechat",
            "date": "2026-08-15",
            "title": TITLE,
            "core_question": CORE_QUESTION,
            "core_question_tags": sorted(CORE_QUESTION_TAGS),
            "status": "production_ready_revision",
        }
    ]
    hit = same_channel_core_question_blocked(
        channel="wechat",
        candidate_core_question="点位有销量却不赚钱，用周表算清单点贡献再决定撤点",
        candidate_tags={"单点贡献", "撤点", "周表"},
        existing=existing,
        candidate_date="2026-08-17",
    )
    assert hit is not None
    assert hit["blocked"] is True
    assert CANCEL_REASON_TOPIC_OVERLAP in hit["reason"] or "overlap" in hit["reason"]
    with pytest.raises(ValueError, match="core-question overlap"):
        assert_no_same_channel_core_question_overlap(
            channel="wechat",
            candidate_core_question="点位有销量却不赚钱，用周表算清单点贡献再决定撤点",
            candidate_tags={"单点贡献", "撤点"},
            existing=existing,
            candidate_date="2026-08-17",
        )


def test_same_channel_14d_allows_dissimilar_or_canceled():
    existing = [
        {
            "piece_id": "o1-wechat-stockout-tieku",
            "channel": "wechat",
            "date": "2026-08-17",
            "title": "柜机缺货先查这7步",
            "core_question": "柜机缺货信号排查与补货决策",
            "core_question_tags": ["缺货", "补货", "七步"],
            "status": "canceled",
        }
    ]
    # Canceled rows are ignored.
    assert (
        same_channel_core_question_blocked(
            channel="wechat",
            candidate_core_question=CORE_QUESTION,
            candidate_tags=CORE_QUESTION_TAGS,
            existing=existing,
            candidate_date="2026-08-15",
        )
        is None
    )
    # Different channel allowed.
    existing_live = [
        {
            "piece_id": "x",
            "channel": "zhihu",
            "date": "2026-08-15",
            "title": TITLE,
            "core_question": CORE_QUESTION,
            "core_question_tags": sorted(CORE_QUESTION_TAGS),
            "status": "draft_saved",
        }
    ]
    assert (
        same_channel_core_question_blocked(
            channel="wechat",
            candidate_core_question=CORE_QUESTION,
            candidate_tags=CORE_QUESTION_TAGS,
            existing=existing_live,
            candidate_date="2026-08-16",
        )
        is None
    )
    # Outside 14d window allowed even if similar.
    far = [
        {
            "piece_id": "old",
            "channel": "wechat",
            "date": "2026-07-01",
            "title": TITLE,
            "core_question": CORE_QUESTION,
            "core_question_tags": sorted(CORE_QUESTION_TAGS),
            "status": "published",
        }
    ]
    assert (
        same_channel_core_question_blocked(
            channel="wechat",
            candidate_core_question=CORE_QUESTION,
            candidate_tags=CORE_QUESTION_TAGS,
            existing=far,
            candidate_date="2026-08-15",
        )
        is None
    )
