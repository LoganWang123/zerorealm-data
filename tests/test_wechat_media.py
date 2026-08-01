import json

from publishing.article import Article, ArticleMeta
from publishing.asset_manager import AssetManager
from publishing.config import PublishConfig
from publishing.media_storage import LocalMediaStorage
from publishing.models import (
    MediaAsset,
    MediaBundle,
    MediaReference,
    PublishStatus,
    RenderContext,
    RenderResult,
    WechatMetadata,
)
from publishing.wechat.client import WechatClient
from publishing.wechat.publisher import WechatPublisher
from publishing.wechat.renderer import WechatRenderer


def generated_bundle(tmp_path):
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"cover")
    body_images = []
    for index in range(1, 4):
        path = tmp_path / f"body-{index}.png"
        path.write_bytes(f"body-{index}".encode())
        body_images.append(
            MediaAsset(
                role=f"body_{index}",
                local_path=str(path),
                mime="image/png",
            )
        )
    video = tmp_path / "short.mp4"
    video.write_bytes(b"video")
    return MediaBundle(
        cover=MediaAsset("cover", str(cover), "image/png"),
        body_images=body_images,
        video=MediaAsset("short_video", str(video), "video/mp4"),
    )


def test_renderer_inserts_three_body_images_and_video_placeholder(tmp_path):
    article = Article(
        metadata=ArticleMeta("article-1", "daily-1", "daily", 1),
        title="零域日报",
        date="2026-07-29",
        summary=["summary"],
    )
    article.media_bundle = generated_bundle(tmp_path)
    article.cover = article.media_bundle.cover.local_path
    article.discussion = "回复柜机数量和饮料缺货率。"
    context = RenderContext(config=PublishConfig(), asset_manager=AssetManager())

    rendered = WechatRenderer(LocalMediaStorage()).render(article, context)

    assert [asset.role for asset in rendered.media] == [
        "body_1",
        "body_2",
        "body_3",
    ]
    assert rendered.video.role == "short_video"
    for role in ("body_1", "body_2", "body_3"):
        assert f"zr-media://{role}" in rendered.body
    assert "zr-video://short_video" in rendered.body
    assert "回复柜机数量和饮料缺货率" in rendered.body


def test_renderer_uses_explicit_local_images_without_media_generation(tmp_path):
    first = tmp_path / "local-first.png"
    second = tmp_path / "local-second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    article = Article(
        metadata=ArticleMeta("article-1", "daily-1", "daily", 1),
        title="Daily",
        date="2026-08-01",
        summary=["summary"],
        cover=str(first),
        inline_images=[str(first), str(second)],
    )
    context = RenderContext(config=PublishConfig(), asset_manager=AssetManager())

    rendered = WechatRenderer(LocalMediaStorage()).render(article, context)

    assert [asset.role for asset in rendered.media] == ["inline_1", "inline_2"]
    assert [asset.local_path for asset in rendered.media] == [str(first), str(second)]
    assert "zr-media://inline_1" in rendered.body
    assert "zr-media://inline_2" in rendered.body


class FakeWechatClient:
    def __init__(self, fail_video=False):
        self.created = []
        self.content_uploads = []
        self.video_uploads = []
        self.fail_video = fail_video

    def upload_content_image(self, path):
        self.content_uploads.append(path)
        index = len(self.content_uploads)
        return f"https://mmbiz.qpic.cn/body-{index}.png"

    def upload_permanent_video(self, path, title, introduction):
        self.video_uploads.append((path, title, introduction))
        if self.fail_video:
            raise RuntimeError("video permission denied")
        return {"media_id": "wechat-video-id"}

    def upload_permanent_image(self, path):
        return {"media_id": "wechat-cover-id"}

    def create_draft(self, articles):
        self.created.append(articles)
        return "draft-id"

    def update_draft(self, media_id, index, article):
        return {}


def render_result_with_media(tmp_path):
    bundle = generated_bundle(tmp_path)
    return RenderResult(
        article_uuid="article-1",
        title="零域日报",
        body=(
            '<img src="zr-media://body_1">'
            '<img src="zr-media://body_2">'
            '<img src="zr-media://body_3">'
            "zr-video://short_video"
        ),
        summary="summary",
        cover=MediaReference(local_path=bundle.cover.local_path),
        author="ZeroRealm AI",
        media=[
            MediaReference(
                local_path=asset.local_path,
                mime=asset.mime,
                role=asset.role,
            )
            for asset in bundle.body_images
        ],
        video=MediaReference(
            local_path=bundle.video.local_path,
            mime=bundle.video.mime,
            role=bundle.video.role,
        ),
        channel_metadata=WechatMetadata(digest="summary"),
    )


def test_publisher_uploads_body_images_and_video_before_creating_draft(tmp_path):
    client = FakeWechatClient()

    result = WechatPublisher(client).publish(render_result_with_media(tmp_path))

    assert result.status == PublishStatus.SUCCESS
    assert len(client.content_uploads) == 3
    assert len(client.video_uploads) == 1
    content = client.created[0][0]["content"]
    assert "zr-media://" not in content
    assert "zr-video://" not in content
    assert "https://mmbiz.qpic.cn/body-1.png" in content
    assert "wechat-video-id" in content


def test_video_upload_failure_blocks_draft_creation(tmp_path):
    client = FakeWechatClient(fail_video=True)

    result = WechatPublisher(client).publish(render_result_with_media(tmp_path))

    assert result.status == PublishStatus.FAILED
    assert "Video upload failed" in result.message
    assert client.created == []


class FakeResponse:
    content = b'{"media_id":"video-media-id"}'

    def json(self):
        return {"media_id": "video-media-id"}


class RecordingSession:
    def __init__(self):
        self.request = None

    def post(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeResponse()


def test_client_uploads_video_as_permanent_material(tmp_path, monkeypatch):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"video")
    client = WechatClient("app-id", "app-secret")
    session = RecordingSession()
    client._session = session
    monkeypatch.setattr(client, "get_access_token", lambda: "access-token")

    result = client.upload_permanent_video(
        str(video),
        title="零域日报短视频",
        introduction="每日零售行业情报",
    )

    assert result["media_id"] == "video-media-id"
    url, request = session.request
    assert url.endswith("/cgi-bin/material/add_material")
    assert request["params"] == {"access_token": "access-token", "type": "video"}
    assert json.loads(request["data"]["description"]) == {
        "title": "零域日报短视频",
        "introduction": "每日零售行业情报",
    }
