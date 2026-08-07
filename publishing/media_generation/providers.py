"""Local-only image generation providers. Agnes is never used here."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from publishing.media_generation.errors import (
    AgnesImageGenerationDisabled,
    LocalImageGeneratorUnavailable,
)
from publishing.media_generation.programmatic import (
    render_brand_cover,
    render_editorial_illustration,
)


@runtime_checkable
class ImageGenerationProvider(Protocol):
    image_model: str
    video_model: str

    def generate_image(self, prompt: str, size: str) -> bytes: ...

    def generate_video(
        self,
        prompt: str,
        aspect_ratio: str,
        duration_seconds: int,
        poll_interval_seconds: int,
        poll_timeout_seconds: int,
    ) -> bytes: ...


def parse_size(size: str) -> tuple[int, int]:
    width_s, height_s = size.lower().split("x", 1)
    return int(width_s), int(height_s)


class LocalImageGenerator:
    """COMPATIBILITY helper for programmatic brand covers only.

    Scene photography must come from IDE-native MediaJob attach workflow.
    Do not treat ZEROREALM_LOCAL_IMAGE_CMD as the core ZeroRealm image strategy.
    Never calls Agnes.
    """

    def __init__(
        self,
        *,
        image_model: str = "programmatic-brand",
        video_model: str = "disabled",
        allow_programmatic: bool = True,
        local_command: str | None = None,
        call_counter: list[str] | None = None,
        allow_programmatic_scenes: bool = False,
    ):
        self.image_model = image_model
        self.video_model = video_model
        self.allow_programmatic = allow_programmatic
        self.allow_programmatic_scenes = allow_programmatic_scenes
        self.local_command = local_command or os.getenv("ZEROREALM_LOCAL_IMAGE_CMD", "")
        self._calls = call_counter if call_counter is not None else []

    @property
    def available(self) -> bool:
        return bool(self.local_command) or self.allow_programmatic

    def generate_image(self, prompt: str, size: str) -> bytes:
        self._calls.append("generate_image")
        width, height = parse_size(size)
        if self.local_command:
            return self._run_local_command(prompt, width, height)
        if not self.allow_programmatic:
            raise LocalImageGeneratorUnavailable(
                "Programmatic templates disabled; create a MediaJob for IDE-native generation"
            )
        # Brand covers / OG-like wide banners only — never fake scene photography.
        if width >= height * 2 or (width == 900 and height == 383) or (
            width == 1200 and height == 630
        ):
            title = _extract_title(prompt)
            return render_brand_cover(width=width, height=height, title=title)
        if self.allow_programmatic_scenes:
            return render_editorial_illustration(width=width, height=height)
        raise LocalImageGeneratorUnavailable(
            "Scene images require IDE-native MediaJob generation; "
            "programmatic placeholders must not impersonate AI photography"
        )

    def generate_video(
        self,
        prompt: str,
        aspect_ratio: str,
        duration_seconds: int,
        poll_interval_seconds: int,
        poll_timeout_seconds: int,
    ) -> bytes:
        self._calls.append("generate_video")
        raise LocalImageGeneratorUnavailable(
            "Local video generation is not configured; write a prompt package instead"
        )

    def _run_local_command(self, prompt: str, width: int, height: int) -> bytes:
        out = Path(".cache") / "local-image-out.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        cmd = self.local_command.format(
            prompt=prompt,
            width=width,
            height=height,
            output=str(out),
        )
        completed = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or not out.is_file():
            raise LocalImageGeneratorUnavailable(
                "local image command failed; prompt package required"
            )
        return out.read_bytes()


class DisabledAgnesImageGenerator:
    """Guard that ensures Agnes image APIs are never invoked in production paths."""

    image_model = "agnes-deprecated"
    video_model = "agnes-deprecated"

    def generate_image(self, prompt: str, size: str) -> bytes:
        raise AgnesImageGenerationDisabled()

    def generate_video(
        self,
        prompt: str,
        aspect_ratio: str,
        duration_seconds: int,
        poll_interval_seconds: int,
        poll_timeout_seconds: int,
    ) -> bytes:
        raise AgnesImageGenerationDisabled()


def _extract_title(prompt: str) -> str:
    for marker in ("标题：", "title:", "Title:"):
        if marker in prompt:
            part = prompt.split(marker, 1)[1].strip()
            return part.split("\n", 1)[0][:40]
    # Fall back to a short slice of the prompt without dumping the whole thing
    compact = " ".join(prompt.split())
    return compact[:36] if compact else "ZeroRealm"


def build_default_image_provider(
    *,
    provider_name: str,
    image_model: str,
    allow_programmatic: bool = True,
) -> ImageGenerationProvider:
    """Factory used by PublishWorkflow. Never returns a live Agnes client."""
    name = (provider_name or "local").strip().lower()
    if name in {"agnes", "agnes-ai"}:
        raise AgnesImageGenerationDisabled(
            "config media.provider=agnes is deprecated; use provider=local"
        )
    if name not in {"local", "programmatic", "local-programmatic"}:
        raise LocalImageGeneratorUnavailable(f"unsupported image provider '{provider_name}'")
    return LocalImageGenerator(
        image_model=image_model or "local-programmatic",
        allow_programmatic=allow_programmatic,
    )
