import hashlib
import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from publishing.config import PublishConfig
from publishing.article import Article, ArticleMeta
from publishing.media_generation.homepage import generate_homepage_media
from publishing.media_generation.prompts import (
    build_daily_prompts,
    build_homepage_prompts,
)
from publishing.media_generation.service import MediaGenerationService
from publishing.media_generation.validation import MediaProbe, MediaValidator, probe_media
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


def test_homepage_prompts_define_three_distinct_retail_intelligence_scenes():
    prompts = build_homepage_prompts()

    assert prompts.version == "homepage-v2"
    assert len(prompts.video_scenes) == 3
    assert "零售信号" in prompts.video_scenes[0]
    assert "结构化知识" in prompts.video_scenes[1]
    assert "经营决策" in prompts.video_scenes[2]
    for prompt in (prompts.cover, *prompts.video_scenes):
        assert "禁止任何文字" in prompt
        assert "不循环" in prompt


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


def test_probe_media_accepts_explicit_ffprobe_path(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42content")
    ffprobe_path = tmp_path / "tools" / "ffprobe.exe"
    ffprobe_path.parent.mkdir()
    ffprobe_path.write_bytes(b"executable")
    calls = []
    monkeypatch.setenv("FFPROBE_PATH", str(ffprobe_path))
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **kwargs: (
            calls.append((command, kwargs))
            or SimpleNamespace(
                stdout=json.dumps(
                    {
                        "streams": [{"width": 1920, "height": 1080}],
                        "format": {"duration": "15.0"},
                    }
                )
            )
        ),
    )

    probe = probe_media(video_path)

    assert probe == MediaProbe(
        mime="video/mp4",
        width=1920,
        height=1080,
        duration_seconds=15,
    )
    assert calls[0][0][0] == str(ffprobe_path)


def test_homepage_generation_is_fixed_until_force_is_explicit(tmp_path):
    website_root = tmp_path / "website"
    client = FakeAgnesClient()

    first = generate_homepage_media(
        client=client,
        website_root=website_root,
        force=False,
        validator=lambda image_path, video_path: None,
    )

    manifest_path = website_root / "public" / "media" / "home" / "homepage-media.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert first == manifest_path
    assert manifest["image"]["src"] == "/media/home/hero.png"
    assert manifest["video"]["src"] == "/media/home/showcase.mp4"
    assert manifest["video"]["poster"] == "/media/home/hero.png"
    assert len(client.image_calls) == 1
    assert len(client.video_calls) == 1

    with pytest.raises(FileExistsError, match="--force"):
        generate_homepage_media(
            client=client,
            website_root=website_root,
            force=False,
            validator=lambda image_path, video_path: None,
        )

    generate_homepage_media(
        client=client,
        website_root=website_root,
        force=True,
        validator=lambda image_path, video_path: None,
    )
    assert len(client.image_calls) == 2
    assert len(client.video_calls) == 2


def test_homepage_generation_resumes_complete_partial_files(tmp_path):
    website_root = tmp_path / "website"
    home_dir = website_root / "public" / "media" / "home"
    home_dir.mkdir(parents=True)
    image_content = b"\x89PNG\r\n\x1a\n" + b"existing-image"
    video_content = b"\x00\x00\x00\x18ftypmp42" + b"existing-video"
    image_partial = home_dir / "hero.png.partial"
    video_partial = home_dir / "showcase.mp4.partial"
    image_partial.write_bytes(image_content)
    video_partial.write_bytes(video_content)
    client = FakeAgnesClient()
    validated = []

    manifest_path = generate_homepage_media(
        client=client,
        website_root=website_root,
        validator=lambda image_path, video_path: validated.append(
            (image_path, video_path)
        ),
    )

    assert validated == [(image_partial, video_partial)]
    assert client.image_calls == []
    assert client.video_calls == []
    assert (home_dir / "hero.png").read_bytes() == image_content
    assert (home_dir / "showcase.mp4").read_bytes() == video_content
    assert not image_partial.exists()
    assert not video_partial.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["image"]["sha256"] == hashlib.sha256(image_content).hexdigest()
    assert manifest["video"]["sha256"] == hashlib.sha256(video_content).hexdigest()
