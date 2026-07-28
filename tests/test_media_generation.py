from publishing.config import PublishConfig
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
