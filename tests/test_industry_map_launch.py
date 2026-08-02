import json

from publishing.wechat.client import WechatClient
from publishing.wechat.industry_map_launch import (
    ARTICLE_TITLE,
    build_industry_map_article,
    create_verified_draft,
)


class FakeDraftClient:
    def __init__(self):
        self.created_articles = []

    def create_draft(self, articles):
        self.created_articles = articles
        return "draft-media-id"

    def get_draft(self, media_id):
        assert media_id == "draft-media-id"
        return {"news_item": self.created_articles}


def test_article_drives_download_and_public_case_submissions():
    article = build_industry_map_article(
        ["https://mmbiz.qpic.cn/operating-loop", "https://mmbiz.qpic.cn/evidence-map"],
        thumb_media_id="cover-media-id",
    )

    assert article["title"] == ARTICLE_TITLE
    assert article["thumb_media_id"] == "cover-media-id"
    assert article["content"].count("<img") == 2
    assert "https://zerorealm.tech/research/industry-map" in article["content"]
    assert "公开案例征集｜资料纠错｜行业合作" in article["content"]
    assert "hi@zerorealm.tech" in article["content"]
    assert "运营商访谈" not in article["content"]
    assert "市场规模" not in article["content"]


def test_verified_draft_requires_api_readback_title_match():
    client = FakeDraftClient()
    article = build_industry_map_article(
        ["https://mmbiz.qpic.cn/one", "https://mmbiz.qpic.cn/two"],
        thumb_media_id="cover-media-id",
    )

    media_id = create_verified_draft(client, article)

    assert media_id == "draft-media-id"
    assert client.created_articles == [article]


def test_article_payload_is_utf8_json_serializable():
    article = build_industry_map_article(
        ["https://mmbiz.qpic.cn/one", "https://mmbiz.qpic.cn/two"],
        thumb_media_id="cover-media-id",
    )

    encoded = json.dumps(article, ensure_ascii=False).encode("utf-8")

    assert "中国无人零售产业图谱".encode("utf-8") in encoded


def test_get_draft_posts_media_id_to_readback_endpoint(monkeypatch):
    client = WechatClient("app-id", "app-secret")
    monkeypatch.setattr(client, "get_access_token", lambda: "token")
    captured = {}

    class Response:
        content = json.dumps(
            {"news_item": [{"title": ARTICLE_TITLE}]}, ensure_ascii=False
        ).encode("utf-8")

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(client._session, "post", post)

    result = client.get_draft("draft-media-id")

    assert captured["url"].endswith("/cgi-bin/draft/get")
    assert json.loads(captured["data"].decode("utf-8")) == {
        "media_id": "draft-media-id"
    }
    assert result["news_item"][0]["title"] == ARTICLE_TITLE
