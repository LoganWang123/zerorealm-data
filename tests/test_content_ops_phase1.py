"""Tests for content-ops phase 1 helpers (no live WeChat / LLM)."""

from __future__ import annotations

import json
from pathlib import Path

from growth.combat_pack import CAMPAIGN, TOOL_PAGE_URL
from growth.content_ops_phase1 import (
    IMAGE_STATUS,
    WECHAT_STOCKOUT_PIECE_ID,
    ZHIHU_PIECE_ID,
    build_phase1_manifest,
    build_wechat_stockout_packet,
    build_zhihu_five_metrics_packet,
    inspect_draft_payload,
    match_plan_overlap,
    summarize_draft_item,
)
from publishing.wechat.client import WechatClient

ROOT = Path(__file__).resolve().parents[1]


def test_list_drafts_posts_batchget_payload(monkeypatch):
    client = WechatClient("app-id", "app-secret")
    monkeypatch.setattr(client, "get_access_token", lambda: "token")
    captured = {}

    class Response:
        content = json.dumps(
            {"total_count": 1, "item_count": 1, "item": []}, ensure_ascii=False
        ).encode("utf-8")

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(client._session, "post", post)
    result = client.list_drafts(offset=0, count=20, no_content=0)
    assert captured["url"].endswith("/cgi-bin/draft/batchget")
    assert json.loads(captured["data"].decode("utf-8")) == {
        "offset": 0,
        "count": 20,
        "no_content": 0,
    }
    assert result["total_count"] == 1


def test_inspect_draft_payload_records_overlap_without_bodies():
    payload = {
        "total_count": 2,
        "item_count": 2,
        "item": [
            {
                "media_id": "media-five",
                "update_time": 1700000000,
                "content": {
                    "news_item": [
                        {
                            "title": "智能柜周经营复盘：先填这五个过程指标",
                            "digest": "x" * 200,
                            "content": "<p>SHOULD_NOT_APPEAR_IN_REPORT</p>",
                            "thumb_media_id": "thumb-1",
                        }
                    ]
                },
            },
            {
                "media_id": "media-other",
                "update_time": 1700001000,
                "content": {
                    "news_item": [
                        {
                            "title": "无关旧稿",
                            "digest": "old",
                            "content": "<p>body</p>",
                        }
                    ]
                },
            },
        ],
    }
    report = inspect_draft_payload(payload)
    assert report["mode"] == "read_only_list"
    assert report["safety"]["delete"] is False
    assert report["safety"]["publish"] is False
    assert report["safety"]["mass_send"] is False
    assert report["item_count"] == 2
    assert report["drafts"][0]["media_status"]["any_thumb_present"] is True
    assert len(report["drafts"][0]["articles"][0]["digest"]) <= 160
    dumped = json.dumps(report, ensure_ascii=False)
    assert "SHOULD_NOT_APPEAR_IN_REPORT" not in dumped
    assert any(o["piece_id"] == "w1-wechat-five-metrics" for o in report["plan_overlap"])


def test_match_plan_overlap_stockout():
    hits = match_plan_overlap(["柜机缺货排查清单：先查这 7 步再补货"])
    assert any(h["piece_id"] == "w1-wechat-stockout" for h in hits)


def test_summarize_draft_item_without_content_block():
    summary = summarize_draft_item({"media_id": "m1", "update_time": 1})
    assert summary["titles"] == []
    assert summary["media_status"]["any_thumb_present"] is False


def test_packets_have_single_cta_utm_and_awaiting_images():
    zhihu = build_zhihu_five_metrics_packet(body_markdown="# hi\n")
    wechat = build_wechat_stockout_packet(body_markdown="# hi\n")
    assert zhihu["piece_id"] == ZHIHU_PIECE_ID
    assert wechat["piece_id"] == WECHAT_STOCKOUT_PIECE_ID
    assert zhihu["image_status"] == IMAGE_STATUS
    assert wechat["image_status"] == IMAGE_STATUS
    assert zhihu["cta"]["url"].startswith(TOOL_PAGE_URL)
    assert f"utm_campaign={CAMPAIGN}" in zhihu["cta"]["url"]
    assert "utm_content=five_metrics_qa" in zhihu["cta"]["url"]
    assert "utm_source=zhihu" in zhihu["cta"]["url"]
    assert "utm_content=stockout_checklist" in wechat["cta"]["url"]
    assert "utm_source=wechat" in wechat["cta"]["url"]
    assert zhihu["auto_publish"] is False
    assert wechat["auto_publish"] is False
    assert zhihu["llm_api_used"] is False
    assert all(b["status"] == IMAGE_STATUS for b in zhihu["image_briefs"])
    assert all(b["status"] == IMAGE_STATUS for b in wechat["image_briefs"])


def test_phase1_manifest_flags_five_metrics_exception():
    inspection = {
        "total_count": 1,
        "item_count": 1,
        "plan_overlap": [
            {
                "media_id": "media-five",
                "piece_id": "w1-wechat-five-metrics",
                "matched_hints": ["五个过程指标"],
                "titles": ["智能柜周经营复盘：先填这五个过程指标"],
            }
        ],
        "safety": {"delete": False, "publish": False},
    }
    zhihu = build_zhihu_five_metrics_packet(body_markdown="a")
    wechat = build_wechat_stockout_packet(body_markdown="b")
    manifest = build_phase1_manifest(
        inspection=inspection,
        zhihu_packet=zhihu,
        wechat_packet=wechat,
        article_source_paths={
            ZHIHU_PIECE_ID: "content/ops_packets/2026-08-15/w1-zhihu-five-metrics.md",
            WECHAT_STOCKOUT_PIECE_ID: "content/ops_packets/2026-08-15/w1-wechat-stockout.md",
        },
    )
    assert manifest["owner_github"] == "LoganWang123"
    assert manifest["wechat_draft_inspection"]["five_metrics_wechat_draft_present"] is True
    assert len(manifest["packets"]) == 2


def test_article_sources_exist_and_contain_cta():
    zhihu = (
        ROOT / "content/ops_packets/2026-08-15/w1-zhihu-five-metrics.md"
    ).read_text(encoding="utf-8")
    wechat = (
        ROOT / "content/ops_packets/2026-08-15/w1-wechat-stockout.md"
    ).read_text(encoding="utf-8")
    assert "utm_content=five_metrics_qa" in zhihu
    assert "utm_content=stockout_checklist" in wechat
    assert "停止规则" in wechat
    assert zhihu.count("https://zerorealm.tech/tools/smart-cabinet-weekly-review") == 1
    assert wechat.count("https://zerorealm.tech/tools/smart-cabinet-weekly-review") == 1
