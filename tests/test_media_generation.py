import hashlib
from pathlib import Path

from publishing.config import PublishConfig
from publishing.article import Article, ArticleMeta
from publishing.media_generation.prompts import build_daily_prompts
from publishing.media_generation.service import MediaGenerationService
from publishing.media_generation.validation import MediaProbe, MediaValidator
from publishing.models import MediaAsset, MediaBundle


def test_publish_config_loads_media_generation_settings(tmp_path):
    config_path = tmp_path / "publish.yaml"
    config_path.write_text(
        "media:\n"
        "  enabled: true\n"
        "  provider: agnes\n"
        "  image_model: agnes-image-2.1-flash\n"
        "  video_model: agnes-video-v2.0\n"
        "  body_image_count: 3\n"
        "  video_duration_seconds: 15\n"
        '  video_aspect_ratio: "9:16"\n',
        encoding="utf-8",
    )

    config = PublishConfig.load(str(config_path))

    assert config.media.enabled is True
    assert config.media.provider == "agnes"
    assert config.media.image_model == "agnes-image-2.1-flash"
    assert config.media.video_model == "agnes-video-v2.0"
    assert config.media.body_image_count == 3
    assert config.media.video_duration_seconds == 15
    assert config.media.video_aspect_ratio == "9:16"


def test_media_bundle_returns_assets_in_publish_order():
    cover = MediaAsset(role="cover", local_path="cover.png", mime="image/png")
    body_images = [
        MediaAsset(
            role=f"body_{index}",
            local_path=f"body-{index}.png",
            mime="image/png",
        )
        for index in range(1, 4)
    ]
    video = MediaAsset(
        role="short_video",
        local_path="short-video.mp4",
        mime="video/mp4",
    )

    bundle = MediaBundle(cover=cover, body_images=body_images, video=video)

    assert bundle.all_assets() == [cover, *body_images, video]


class FakeAgnesClient:
    image_model = "agnes-image-2.1-flash"
    video_model = "agnes-video-v2.0"

    def __init__(self):
        self.image_calls = []
        self.video_calls = []

    def generate_image(self, prompt, size):
        self.image_calls.append((prompt, size))
        return b"\x89PNG\r\n\x1a\n" + b"generated-image"

    def generate_video(
        self,
        prompt,
        aspect_ratio,
        duration_seconds,
        poll_interval_seconds,
        poll_timeout_seconds,
    ):
        self.video_calls.append(
            (
                prompt,
                aspect_ratio,
                duration_seconds,
                poll_interval_seconds,
                poll_timeout_seconds,
            )
        )
        return b"\x00\x00\x00\x18ftypmp42" + b"generated-video"


def daily_article(content_revision=1):
    return Article(
        metadata=ArticleMeta(
            uuid="article-2026-07-29",
            slug="daily-2026-07-29",
            source="daily",
            issue=4,
            content_revision=content_revision,
        ),
        title="零域日报 No.4",
        date="2026-07-29",
        summary=["即时零售进入精细化运营阶段", "AI 正在改变门店决策"],
    )


def media_config(tmp_path):
    config = PublishConfig()
    config.media.poll_interval_seconds = 0
    config.media.poll_timeout_seconds = 30
    return config.media


def test_daily_prompts_are_role_specific_and_include_article_context():
    prompts = build_daily_prompts(daily_article(), body_image_count=3)

    assert prompts.version == "daily-v1"
    assert "零域日报 No.4" in prompts.cover
    assert "封面" in prompts.cover
    assert len(prompts.body_images) == 3
    assert "开篇" in prompts.body_images[0]
    assert "核心分析" in prompts.body_images[1]
    assert "决策" in prompts.body_images[2]
    assert "9:16" in prompts.video
    assert "15 秒" in prompts.video


def test_daily_generation_reuses_valid_manifest_without_provider_calls(tmp_path):
    client = FakeAgnesClient()
    service = MediaGenerationService(
        client=client,
        config=media_config(tmp_path),
        output_root=tmp_path,
    )

    first = service.generate_daily(daily_article())
    second = service.generate_daily(daily_article())

    assert [asset.local_path for asset in first.all_assets()] == [
        asset.local_path for asset in second.all_assets()
    ]
    assert len(client.image_calls) == 4
    assert len(client.video_calls) == 1
    assert (tmp_path / "2026-07-29" / "media-manifest.json").exists()


def test_daily_generation_regenerates_only_a_missing_asset(tmp_path):
    client = FakeAgnesClient()
    service = MediaGenerationService(
        client=client,
        config=media_config(tmp_path),
        output_root=tmp_path,
    )
    first = service.generate_daily(daily_article())
    Path(first.body_images[1].local_path).unlink()

    service.generate_daily(daily_article())

    assert len(client.image_calls) == 5
    assert len(client.video_calls) == 1


def test_media_validator_reports_hash_and_video_aspect_ratio_errors(tmp_path):
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\ncontent")
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42content")
    wrong_hash = "0" * 64

    bundle = MediaBundle(
        cover=MediaAsset(
            role="cover",
            local_path=str(image_path),
            mime="image/png",
            sha256=wrong_hash,
        ),
        body_images=[],
        video=MediaAsset(
            role="short_video",
            local_path=str(video_path),
            mime="video/mp4",
            sha256=hashlib.sha256(video_path.read_bytes()).hexdigest(),
        ),
    )
    validator = MediaValidator(
        expected_body_images=0,
        expected_video_aspect_ratio="9:16",
        probe=lambda path: MediaProbe(
            mime="video/mp4" if path.suffix == ".mp4" else "image/png",
            width=1280,
            height=720,
            duration_seconds=15 if path.suffix == ".mp4" else 0,
        ),
    )

    errors = validator.validate(bundle)

    assert any("cover hash mismatch" in error for error in errors)
    assert any("short_video aspect ratio" in error for error in errors)
