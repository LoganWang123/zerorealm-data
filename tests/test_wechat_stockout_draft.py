"""Tests for authorized WeChat stockout draft-only creation (no live API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from growth.combat_pack import CAMPAIGN, TOOL_PAGE_URL
from growth.wechat_stockout_draft import (
    APPROVED_TITLE,
    AUTHOR,
    PRESERVED_UNRELATED_TITLE,
    WechatDraftSafetyError,
    apply_wechat_draft_created,
    assert_single_approved_cta,
    build_article_payload,
    build_stockout_html,
    create_authorized_stockout_draft,
    count_cta_occurrences,
    truncate_utf8,
    verify_local_images,
    verify_readback,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "data/growth/content-packet-w1-wechat-stockout-2026-08-15.json"
MODULE_PATH = ROOT / "growth/wechat_stockout_draft.py"
SCRIPT_PATH = ROOT / "scripts/create_wechat_stockout_draft.py"
CTA_URL = (
    "https://zerorealm.tech/tools/smart-cabinet-weekly-review"
    "?utm_source=wechat&utm_medium=article"
    f"&utm_campaign={CAMPAIGN}&utm_content=stockout_checklist"
)
UNRELATED_MEDIA_ID = "csbrZswCx_unrelated_single_point"


def _packet() -> dict:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def _unrelated_item() -> dict:
    return {
        "media_id": UNRELATED_MEDIA_ID,
        "update_time": 1786251549,
        "content": {
            "news_item": [
                {
                    "title": PRESERVED_UNRELATED_TITLE,
                    "author": "ZeroRealm AI",
                    "digest": "点位有流水，不等于点位赚钱。",
                    "thumb_media_id": "thumb-unrelated",
                }
            ]
        },
    }


class FakeDraftClient:
    def __init__(self, extra_items: list[dict] | None = None):
        self.calls: list[str] = []
        self.items = [_unrelated_item()] + list(extra_items or [])
        self.created_articles: list[dict] = []
        self.deleted: list[str] = []
        self.updated: list[str] = []
        self.published: list[str] = []
        self.mass_sent: list[str] = []
        self.cover_uploads: list[str] = []
        self.body_uploads: list[str] = []

    def list_drafts(self, *, offset: int = 0, count: int = 20, no_content: int = 0) -> dict:
        self.calls.append("list_drafts")
        slice_items = self.items[offset : offset + count]
        return {
            "total_count": len(self.items),
            "item_count": len(slice_items),
            "item": slice_items,
        }

    def upload_permanent_image(self, path: str) -> dict:
        self.calls.append("upload_permanent_image")
        self.cover_uploads.append(path)
        return {"media_id": "thumb-stockout"}

    def upload_content_image(self, path: str) -> str:
        self.calls.append("upload_content_image")
        self.body_uploads.append(path)
        return "https://mmbiz.qpic.cn/stockout-illustration.png"

    def create_draft(self, articles: list[dict]) -> str:
        self.calls.append("create_draft")
        self.created_articles = list(articles)
        self.items.append(
            {
                "media_id": "draft-stockout",
                "update_time": 1786259999,
                "content": {"news_item": list(articles)},
            }
        )
        return "draft-stockout"

    def get_draft(self, media_id: str) -> dict:
        self.calls.append("get_draft")
        for item in self.items:
            if item.get("media_id") == media_id:
                return {"news_item": list((item.get("content") or {}).get("news_item") or [])}
        raise AssertionError(f"unknown media_id {media_id}")

    def delete_draft(self, media_id: str) -> dict:
        self.calls.append("delete_draft")
        self.deleted.append(media_id)
        raise AssertionError("delete_draft must not be called")

    def update_draft(self, media_id: str, index: int, article: dict) -> dict:
        self.calls.append("update_draft")
        self.updated.append(media_id)
        raise AssertionError("update_draft must not be called")

    def submit_publish(self, media_id: str) -> str:
        self.calls.append("submit_publish")
        self.published.append(media_id)
        raise AssertionError("submit_publish must not be called")

    def send_mass_article(self, media_id: str) -> str:
        self.calls.append("send_mass_article")
        self.mass_sent.append(media_id)
        raise AssertionError("send_mass_article must not be called")


def test_source_files_never_call_mutating_or_publish_apis():
    combined = MODULE_PATH.read_text(encoding="utf-8") + SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in (
        ".delete_draft(",
        ".update_draft(",
        ".submit_publish(",
        ".send_mass_article(",
        ".create_mass_article(",
        "freepublish/submit",
        "message/mass/sendall",
        "draft/delete",
        "draft/update",
    ):
        assert forbidden not in combined


def test_html_has_exactly_one_approved_cta_and_illustration():
    packet = _packet()
    html = build_stockout_html(
        packet["body_markdown"],
        illustration_url="https://mmbiz.qpic.cn/stockout-illustration.png",
        cta_url=packet["cta"]["url"],
        cta_copy=packet["cta"]["copy"],
    )
    assert_single_approved_cta(html, packet["cta"]["url"])
    assert count_cta_occurrences(html, packet["cta"]["url"]) == 1
    assert html.count("https://mmbiz.qpic.cn/stockout-illustration.png") == 1
    assert "缺货信号" in html
    assert "停止规则" in html
    assert "可打印清单" in html
    assert "utm_content=stockout_checklist" in html
    assert f"utm_campaign={CAMPAIGN}" in html
    assert TOOL_PAGE_URL in html
    assert "hi@zerorealm.tech" not in html
    assert "mailto:" not in html
    assert html.count("<table") == 2


def test_article_payload_sets_author_digest_and_source_url():
    packet = _packet()
    html = build_stockout_html(
        packet["body_markdown"],
        illustration_url="https://mmbiz.qpic.cn/stockout-illustration.png",
        cta_url=packet["cta"]["url"],
        cta_copy=packet["cta"]["copy"],
    )
    article = build_article_payload(
        title=packet["title"],
        html=html,
        thumb_media_id="thumb-stockout",
        digest=packet["digest"],
        content_source_url=packet["cta"]["url"],
    )
    assert article["author"] == AUTHOR
    assert article["content_source_url"] == packet["cta"]["url"]
    assert len(article["digest"].encode("utf-8")) <= 120
    assert packet["digest"].startswith(article["digest"])
    assert article["need_open_comment"] == 1
    assert article["show_cover_pic"] == 1


def test_create_uploads_images_adds_draft_and_preserves_unrelated():
    client = FakeDraftClient()
    result = create_authorized_stockout_draft(client, packet=_packet(), root=ROOT)

    assert result["status"] == "wechat_draft_created"
    assert result["created"] is True
    assert result["media_id"] == "draft-stockout"
    assert result["exact_title_duplicate"] is False
    assert client.cover_uploads and client.body_uploads
    assert client.created_articles[0]["title"] == APPROVED_TITLE
    assert client.created_articles[0]["author"] == AUTHOR
    assert client.created_articles[0]["content_source_url"] == CTA_URL
    assert "create_draft" in client.calls
    assert "get_draft" in client.calls
    assert client.calls.count("list_drafts") >= 2
    assert "delete_draft" not in client.calls
    assert "update_draft" not in client.calls
    assert "submit_publish" not in client.calls
    assert "send_mass_article" not in client.calls
    assert client.deleted == []
    assert result["preserved_unrelated"]["present_before"] is True
    assert result["preserved_unrelated"]["present_after"] is True
    assert PRESERVED_UNRELATED_TITLE in result["post_create"]["titles"]
    assert APPROVED_TITLE in result["post_create"]["titles"]
    assert result["readback"]["cta_count"] == 1
    assert result["readback"]["source_url_match"] is True


def test_exact_title_duplicate_skips_create_and_does_not_overwrite():
    packet = _packet()
    html = build_stockout_html(
        packet["body_markdown"],
        illustration_url="https://mmbiz.qpic.cn/stockout-illustration.png",
        cta_url=packet["cta"]["url"],
        cta_copy=packet["cta"]["copy"],
    )
    existing = {
        "media_id": "already-stockout",
        "update_time": 1,
        "content": {
            "news_item": [
                {
                    "title": APPROVED_TITLE,
                    "author": AUTHOR,
                    "digest": truncate_utf8(packet["digest"]),
                    "content": html,
                    "content_source_url": packet["cta"]["url"],
                    "thumb_media_id": "thumb-existing",
                }
            ]
        },
    }
    client = FakeDraftClient(extra_items=[existing])
    result = create_authorized_stockout_draft(client, packet=packet, root=ROOT)

    assert result["created"] is False
    assert result["exact_title_duplicate"] is True
    assert result["status"] == "wechat_draft_created"
    assert result["media_id"] == "already-stockout"
    assert "create_draft" not in client.calls
    assert "upload_permanent_image" not in client.calls
    assert "update_draft" not in client.calls
    assert "delete_draft" not in client.calls
    assert "get_draft" in client.calls
    assert PRESERVED_UNRELATED_TITLE in result["pre_create"]["titles"]


def test_body_image_falls_back_to_permanent_material_url():
    class OversizedBodyClient(FakeDraftClient):
        def upload_content_image(self, path: str) -> str:
            self.calls.append("upload_content_image")
            raise RuntimeError("media too large")

        def upload_permanent_image(self, path: str) -> dict:
            self.calls.append("upload_permanent_image")
            self.cover_uploads.append(path)
            if path.endswith("illustration.png"):
                return {
                    "media_id": "perm-illustration",
                    "url": "https://mmbiz.qpic.cn/stockout-illustration.png",
                }
            return {"media_id": "thumb-stockout"}

    client = OversizedBodyClient()
    result = create_authorized_stockout_draft(client, packet=_packet(), root=ROOT)
    assert result["created"] is True
    assert "https://mmbiz.qpic.cn/stockout-illustration.png" in client.created_articles[0]["content"]
    assert client.calls.count("upload_permanent_image") == 2


def test_readback_mismatch_fails_closed():
    class BrokenReadback(FakeDraftClient):
        def get_draft(self, media_id: str) -> dict:
            self.calls.append("get_draft")
            article = dict(self.created_articles[0])
            article["title"] = "wrong title"
            return {"news_item": [article]}

    client = BrokenReadback()
    with pytest.raises(WechatDraftSafetyError, match="title mismatch"):
        create_authorized_stockout_draft(client, packet=_packet(), root=ROOT)
    assert client.deleted == []
    assert client.published == []


def test_readback_accepts_wechat_rewritten_data_src_image():
    packet = _packet()
    html = build_stockout_html(
        packet["body_markdown"],
        illustration_url="https://mmbiz.qpic.cn/stockout-illustration.png",
        cta_url=packet["cta"]["url"],
        cta_copy=packet["cta"]["copy"],
    )
    rewritten = html.replace(
        'src="https://mmbiz.qpic.cn/stockout-illustration.png"',
        'data-src="https://mmbiz.qpic.cn/mmbiz_png/rewritten/640?from=appmsg"',
    )
    stored = {
        "news_item": [
            {
                "title": packet["title"],
                "author": AUTHOR,
                "digest": truncate_utf8(packet["digest"]),
                "content": rewritten,
                "content_source_url": packet["cta"]["url"],
                "thumb_media_id": "thumb-stockout",
            }
        ]
    }
    expected = {
        "title": packet["title"],
        "author": AUTHOR,
        "digest": truncate_utf8(packet["digest"]),
        "content_source_url": packet["cta"]["url"],
        "thumb_media_id": "thumb-stockout",
    }
    checks = verify_readback(
        stored, expected, illustration_url="https://mmbiz.qpic.cn/stockout-illustration.png"
    )
    assert checks["illustration_present"] is True
    assert checks["cta_count"] == 1


def test_local_images_match_packet_sha256():
    paths = verify_local_images(_packet(), ROOT)
    assert paths["cover"].name == "cover.png"
    assert paths["illustration"].name == "illustration.png"


def test_second_cta_is_rejected():
    html = '<p><a href="https://zerorealm.tech">home</a> ' f"{CTA_URL}</p>"
    with pytest.raises(WechatDraftSafetyError, match="exactly one"):
        assert_single_approved_cta(html, CTA_URL)


def test_digest_truncates_on_utf8_boundary():
    digest = truncate_utf8("零售AI" * 40, 120)
    assert len(digest.encode("utf-8")) <= 120


def test_apply_manifest_keeps_zhihu_publication_and_sets_draft_status():
    manifest = json.loads(
        (ROOT / "data/growth/content-ops-phase1-manifest-2026-08-15.json").read_text(
            encoding="utf-8"
        )
    )
    packet = _packet()
    result = {
        "status": "wechat_draft_created",
        "media_id": "draft-stockout",
        "created": True,
        "title": APPROVED_TITLE,
        "author": AUTHOR,
        "digest": "d",
        "content_source_url": CTA_URL,
        "exact_title_duplicate": False,
        "safety": {"delete": False, "publish": False, "mass_send": False},
    }
    inspection = {
        "total_count": 2,
        "item_count": 2,
        "plan_overlap": [{"piece_id": "w1-wechat-stockout"}],
    }
    updated_manifest, updated_packet = apply_wechat_draft_created(
        manifest, packet, result=result, inspection=inspection
    )
    assert updated_manifest["status"] == "wechat_draft_created"
    zhihu = next(p for p in updated_manifest["packets"] if p["piece_id"].startswith("w1-zhihu"))
    wechat = next(p for p in updated_manifest["packets"] if p["piece_id"] == "w1-wechat-stockout")
    assert zhihu.get("status") == "zhihu_published" or zhihu.get("public_url")
    assert wechat["status"] == "wechat_draft_created"
    assert updated_packet["status"] == "wechat_draft_created"
    assert updated_packet["draft"]["content_source_url"] == CTA_URL
