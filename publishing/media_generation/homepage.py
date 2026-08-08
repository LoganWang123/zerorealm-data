"""One-shot generation of fixed homepage media."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from publishing.config import MediaConfig
from publishing.media_generation.assembly import (
    assemble_homepage_video,
    normalize_homepage_image,
)
from publishing.media_generation.client import AgnesClient
from publishing.media_generation.prompts import build_homepage_prompts
from publishing.media_generation.validation import probe_media


def generate_homepage_media(
    client: AgnesClient,
    website_root: str | Path,
    *,
    force: bool = False,
    validator: Callable[[Path, Path], None] | None = None,
    image_normalizer: Callable[[Path, Path], None] = normalize_homepage_image,
    video_assembler: Callable[
        [tuple[Path, Path, Path], Path],
        None,
    ] = assemble_homepage_video,
) -> Path:
    """Generate fixed homepage media and replace it only after validation."""
    home_dir = Path(website_root) / "public" / "media" / "home"
    manifest_path = home_dir / "homepage-media.json"
    if manifest_path.exists() and not force:
        raise FileExistsError(
            "Homepage media already exists; pass --force to regenerate it"
        )

    home_dir.mkdir(parents=True, exist_ok=True)
    image_raw = home_dir / "hero.raw.png.partial"
    image_ready = home_dir / "hero.ready.png"
    scene_paths = tuple(
        home_dir / f"scene-{index:02d}.mp4.partial"
        for index in range(1, 4)
    )
    video_ready = home_dir / "showcase.ready.mp4"
    prompts = build_homepage_prompts()

    if not image_raw.exists():
        image_content = client.generate_image(prompts.cover, "1920x1080")
        if not image_content:
            raise ValueError("Homepage image generation returned an empty file")
        image_raw.write_bytes(image_content)

    if not video_ready.exists():
        for prompt, scene_path in zip(
            prompts.video_scenes,
            scene_paths,
            strict=True,
        ):
            if scene_path.exists():
                continue
            scene_content = client.generate_video(
                prompt=prompt,
                aspect_ratio="16:9",
                duration_seconds=5,
                poll_interval_seconds=5,
                poll_timeout_seconds=600,
            )
            if not scene_content:
                raise ValueError("Homepage video generation returned an empty file")
            scene_path.write_bytes(scene_content)

    if not image_ready.exists():
        image_normalizer(image_raw, image_ready)
    if not video_ready.exists():
        video_assembler(scene_paths, video_ready)

    (validator or _validate_homepage_media)(image_ready, video_ready)
    image_content = image_ready.read_bytes()
    video_content = video_ready.read_bytes()

    image_path = home_dir / "hero.png"
    video_path = home_dir / "showcase.mp4"
    image_ready.replace(image_path)
    video_ready.replace(video_path)

    manifest = {
        "prompt_version": prompts.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "image_model": client.image_model,
        "video_model": client.video_model,
        "image": {
            "src": "/media/home/hero.png",
            "alt": "智能柜运营负责人检查柜机商品与库存",
            "width": 1920,
            "height": 1080,
            "sha256": hashlib.sha256(image_content).hexdigest(),
        },
        "video": {
            "src": "/media/home/showcase.mp4",
            "poster": "/media/home/hero.png",
            "title": "从柜机信号到经营动作",
            "width": 1920,
            "height": 1080,
            "duration_seconds": 15,
            "sha256": hashlib.sha256(video_content).hexdigest(),
        },
        "story": [
            {
                "label": "发现信号",
                "description": "检查柜机缺货、陈列与商品周转",
            },
            {
                "label": "核对证据",
                "description": "对照动销、库存与毛利信息",
            },
            {
                "label": "执行动作",
                "description": "完成小范围补货和陈列调整",
            },
        ],
    }
    manifest_partial = manifest_path.with_suffix(".json.partial")
    manifest_partial.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_partial.replace(manifest_path)
    image_raw.unlink(missing_ok=True)
    for scene_path in scene_paths:
        scene_path.unlink(missing_ok=True)
    return manifest_path


def client_from_environment(config: MediaConfig | None = None) -> AgnesClient:
    """DEPRECATED: Agnes homepage generation is disabled.

    Use scripts/generate_local_media.py instead. This helper remains only so
    historical imports fail closed instead of silently calling Agnes.
    """
    del config  # unused — Agnes path disabled
    from publishing.media_generation.errors import AgnesImageGenerationDisabled

    raise AgnesImageGenerationDisabled(
        "homepage Agnes generation is disabled; use local media pipeline"
    )


def _validate_homepage_media(image_path: Path, video_path: Path) -> None:
    image = probe_media(image_path)
    video = probe_media(video_path)
    if image.mime != "image/png":
        raise ValueError("Homepage image is not a valid PNG")
    if (image.width, image.height) != (1920, 1080):
        raise ValueError("Homepage image must be 1920x1080")
    if video.mime != "video/mp4":
        raise ValueError("Homepage video is not a valid MP4")
    if (video.width, video.height) != (1920, 1080):
        raise ValueError("Homepage video must be 1920x1080")
    if not 14 <= video.duration_seconds <= 16:
        raise ValueError("Homepage video duration must be between 14 and 16 seconds")
