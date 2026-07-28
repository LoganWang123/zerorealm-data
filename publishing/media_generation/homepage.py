"""One-shot generation of fixed homepage media."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from publishing.config import MediaConfig
from publishing.media_generation.client import AgnesClient
from publishing.media_generation.prompts import build_homepage_prompts
from publishing.media_generation.validation import probe_media


def generate_homepage_media(
    client: AgnesClient,
    website_root: str | Path,
    *,
    force: bool = False,
    validator: Callable[[Path, Path], None] | None = None,
) -> Path:
    """Generate fixed homepage media and replace it only after validation."""
    home_dir = Path(website_root) / "public" / "media" / "home"
    manifest_path = home_dir / "homepage-media.json"
    if manifest_path.exists() and not force:
        raise FileExistsError(
            "Homepage media already exists; pass --force to regenerate it"
        )

    prompts = build_homepage_prompts()
    image_content = client.generate_image(prompts.cover, "1920x1080")
    video_content = client.generate_video(
        prompt=prompts.video,
        aspect_ratio="16:9",
        duration_seconds=15,
        poll_interval_seconds=5,
        poll_timeout_seconds=600,
    )
    if not image_content or not video_content:
        raise ValueError("Homepage media generation returned an empty file")

    home_dir.mkdir(parents=True, exist_ok=True)
    image_partial = home_dir / "hero.png.partial"
    video_partial = home_dir / "showcase.mp4.partial"
    image_partial.write_bytes(image_content)
    video_partial.write_bytes(video_content)

    (validator or _validate_homepage_media)(image_partial, video_partial)

    image_path = home_dir / "hero.png"
    video_path = home_dir / "showcase.mp4"
    image_partial.replace(image_path)
    video_partial.replace(video_path)

    manifest = {
        "prompt_version": prompts.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "image_model": client.image_model,
        "video_model": client.video_model,
        "image": {
            "src": "/media/home/hero.png",
            "alt": "ZeroRealm AI 将零售行业信号转化为结构化知识",
            "width": 1920,
            "height": 1080,
            "sha256": hashlib.sha256(image_content).hexdigest(),
        },
        "video": {
            "src": "/media/home/showcase.mp4",
            "poster": "/media/home/hero.png",
            "title": "ZeroRealm AI 行业情报工作流",
            "width": 1920,
            "height": 1080,
            "duration_seconds": 15,
            "sha256": hashlib.sha256(video_content).hexdigest(),
        },
    }
    manifest_partial = manifest_path.with_suffix(".json.partial")
    manifest_partial.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_partial.replace(manifest_path)
    return manifest_path


def client_from_environment(config: MediaConfig | None = None) -> AgnesClient:
    """Build an Agnes client without accepting a key from CLI arguments."""
    media = config or MediaConfig()
    api_key = os.getenv("AGNES_API_KEY", "")
    if not api_key:
        raise ValueError("AGNES_API_KEY is required")
    return AgnesClient(
        api_key=api_key,
        base_url=os.getenv(
            "AGNES_BASE_URL",
            "https://apihub.agnes-ai.com/v1",
        ),
        image_model=os.getenv("AGNES_IMAGE_MODEL", media.image_model),
        video_model=os.getenv("AGNES_VIDEO_MODEL", media.video_model),
        video_create_path=os.getenv("AGNES_VIDEO_CREATE_PATH", "/videos"),
        video_status_url_template=os.getenv("AGNES_VIDEO_STATUS_URL_TEMPLATE") or None,
    )


def _validate_homepage_media(image_path: Path, video_path: Path) -> None:
    image = probe_media(image_path)
    video = probe_media(video_path)
    if image.mime != "image/png" or image.width <= 0 or image.height <= 0:
        raise ValueError("Homepage image is not a valid PNG")
    if video.mime != "video/mp4":
        raise ValueError("Homepage video is not a valid MP4")
    target_ratio = 16 / 9
    actual_ratio = video.width / video.height if video.height else 0
    if not actual_ratio or abs(actual_ratio - target_ratio) / target_ratio > 0.02:
        raise ValueError("Homepage video must use a 16:9 aspect ratio")
    if abs(video.duration_seconds - 15) > 3:
        raise ValueError("Homepage video duration must be approximately 15 seconds")
