import json
import sys

import pytest
import requests

import publishing.wechat.client as client_module
from publish import build_parser, main as publish_main
from publishing.config import PublishConfig
from publishing.factory import BuilderContext
from publishing.models import (
    MediaReference,
    PublishStatus,
    RenderResult,
    WechatMetadata,
)
from publishing.wechat.client import WechatAPIError, WechatClient
from publishing.wechat.builder import WechatChannelBuilder
from publishing.wechat.publisher import WechatPublisher


class FakeWechatClient:
    def __init__(self):
        self.created = []
        self.mass_created = []
        self.mass_sent = []
        self.submitted = []

    def upload_permanent_image(self, path):
        return {"media_id": "cover-id"}

    def create_draft(self, articles):
        self.created.append(articles)
        return "draft-id"

    def create_mass_article(self, articles):
        self.mass_created.append(articles)
        return "mass-media-id"

    def update_draft(self, media_id, index, article):
        return {}

    def submit_publish(self, media_id):
        self.submitted.append(media_id)
        return "publish-id"

    def send_mass_article(self, media_id):
        self.mass_sent.append(media_id)
        return "mass-message-id"


def render_result():
    return RenderResult(
        article_uuid="article-1",
        title="Title",
        body="<p>Body</p>",
        summary="Summary",
        cover=MediaReference(local_path=""),
        author="ZeroRealm AI",
        channel_metadata=WechatMetadata(digest="Digest"),
    )


def test_draft_mode_only_creates_draft():
    client = FakeWechatClient()
    result = WechatPublisher(client).publish(render_result())

    assert result.status == PublishStatus.SUCCESS
    assert result.draft_id == "draft-id"
    assert result.publish_id is None
    assert client.submitted == []


def test_publish_mode_submits_created_draft():
    client = FakeWechatClient()
    result = WechatPublisher(client).publish(render_result(), publish_now=True)

    assert result.status == PublishStatus.SUCCESS
    assert result.draft_id == "draft-id"
    assert result.publish_id == "publish-id"
    assert client.submitted == ["draft-id"]


def test_notification_mode_uses_mass_article_without_free_publishing():
    client = FakeWechatClient()

    result = WechatPublisher(client).publish(
        render_result(),
        notify_followers=True,
    )

    assert result.status == PublishStatus.SUCCESS
    assert result.draft_id == "mass-media-id"
    assert result.publish_id == "mass-message-id"
    assert client.created == []
    assert client.submitted == []
    assert client.mass_sent == ["mass-media-id"]


def test_created_article_enables_comments_for_followers():
    client = FakeWechatClient()

    WechatPublisher(client).publish(render_result())

    article = client.created[0][0]
    assert article["need_open_comment"] == 1
    assert article["only_fans_can_comment"] == 1


def test_token_network_error_redacts_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(client_module, "TOKEN_CACHE", tmp_path / "token.json")
    client = WechatClient("secret-app-id", "secret-app-value")

    def fail(*args, **kwargs):
        raise requests.ConnectionError(
            "https://api.weixin.qq.com/cgi-bin/token?secret=secret-app-value"
        )

    monkeypatch.setattr(client._session, "get", fail)

    with pytest.raises(WechatAPIError) as exc_info:
        client.get_access_token()

    message = str(exc_info.value)
    assert "secret-app-id" not in message
    assert "secret-app-value" not in message


def test_authenticated_network_error_redacts_access_token(monkeypatch, tmp_path):
    client = WechatClient("app-id", "app-secret")
    monkeypatch.setattr(client, "get_access_token", lambda: "secret-access-token")
    image = tmp_path / "body.png"
    image.write_bytes(b"image")

    def fail(*args, **kwargs):
        raise requests.ConnectionError(
            "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
            "?access_token=secret-access-token"
        )

    monkeypatch.setattr(client._session, "post", fail)

    with pytest.raises(WechatAPIError) as exc_info:
        client.upload_content_image(str(image))

    assert "secret-access-token" not in str(exc_info.value)


def test_publish_payload_truncates_digest_on_utf8_boundary():
    client = FakeWechatClient()
    rendered = render_result()
    rendered.channel_metadata = WechatMetadata(digest="零售AI" * 30)

    WechatPublisher(client).publish(rendered)

    digest = client.created[0][0]["digest"]
    assert len(digest.encode("utf-8")) <= 120
    assert rendered.channel_metadata.digest.startswith(digest)


def test_create_draft_sends_unescaped_utf8_json(monkeypatch):
    client = WechatClient("app-id", "app-secret")
    monkeypatch.setattr(client, "get_access_token", lambda: "token")
    captured = {}

    class Response:
        def json(self):
            return {"media_id": "draft-id"}

    def post(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(client._session, "post", post)

    client.create_draft([{"title": "零售AI", "content": "<p>中文正文</p>"}])

    assert captured["headers"]["Content-Type"] == "application/json; charset=utf-8"
    assert "零售AI".encode() in captured["data"]
    assert "中文正文".encode() in captured["data"]
    assert b"\\u96f6" not in captured["data"]


def test_mass_notification_uses_all_follower_mpnews_payload(monkeypatch):
    client = WechatClient("app-id", "app-secret")
    monkeypatch.setattr(client, "get_access_token", lambda: "token")
    captured = {}

    class Response:
        content = json.dumps(
            {"errcode": 0, "msg_id": 123456},
        ).encode("utf-8")

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(client._session, "post", post)

    message_id = client.send_mass_article("mass-media-id")

    assert captured["url"].endswith("/cgi-bin/message/mass/sendall")
    assert captured["json"] == {
        "filter": {"is_to_all": True},
        "mpnews": {"media_id": "mass-media-id"},
        "msgtype": "mpnews",
        "send_ignore_reprint": 0,
    }
    assert message_id == "123456"


def test_publish_and_notify_cli_flags_are_mutually_exclusive():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--channel",
                "wechat",
                "--publish",
                "--notify-followers",
            ]
        )


def test_publish_cli_without_channel_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["publish.py"])

    with pytest.raises(SystemExit) as exc_info:
        publish_main()

    assert exc_info.value.code == 1
    assert "usage:" in capsys.readouterr().out


def test_response_json_is_decoded_from_raw_utf8_bytes():
    client = WechatClient("app-id", "app-secret")
    expected = {"errcode": 0, "title": "零售AI"}

    class Response:
        content = json.dumps(expected, ensure_ascii=False).encode("utf-8")

        def json(self):
            return {"errcode": 0, "title": "é›¶å”®AI"}

    assert client._check_response(Response())["title"] == "零售AI"


@pytest.mark.parametrize("mode", ["preview", "dry_run"])
def test_non_publishing_modes_do_not_require_wechat_credentials(monkeypatch, mode):
    monkeypatch.delenv("WECHAT_APPID", raising=False)
    monkeypatch.delenv("WECHAT_SECRET", raising=False)

    target = WechatChannelBuilder.build(
        BuilderContext(config=PublishConfig(), mode=mode)
    )

    assert target.name == "wechat"


def test_publishing_modes_require_wechat_credentials(monkeypatch):
    monkeypatch.delenv("WECHAT_APPID", raising=False)
    monkeypatch.delenv("WECHAT_SECRET", raising=False)

    with pytest.raises(ValueError, match="credentials are missing"):
        WechatChannelBuilder.build(
            BuilderContext(config=PublishConfig(), mode="draft")
        )
