"""Validate generated files before rendering or publication."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from publishing.models import MediaBundle


@dataclass(frozen=True)
class MediaProbe:
    mime: str
    width: int
    height: int
    duration_seconds: float = 0.0


class MediaValidator:
    """Return all blocking media validation errors."""

    def __init__(
        self,
        expected_body_images: int = 3,
        expected_video_aspect_ratio: str = "9:16",
        expected_video_duration_seconds: int = 15,
        probe: Callable[[Path], MediaProbe] | None = None,
    ):
        self._expected_body_images = expected_body_images
        self._expected_video_aspect_ratio = expected_video_aspect_ratio
        self._expected_video_duration_seconds = expected_video_duration_seconds
        self._probe = probe or probe_media

    def validate(self, bundle: MediaBundle) -> list[str]:
        errors: list[str] = []
        if len(bundle.body_images) != self._expected_body_images:
            errors.append(
                f"expected {self._expected_body_images} body images, "
                f"got {len(bundle.body_images)}"
            )

        for asset in bundle.all_assets():
            if not asset.visual_reviewed:
                errors.append(f"{asset.role} has not passed visual review")
            if not asset.text_free:
                errors.append(f"{asset.role} may contain rendered text")
            if not asset.scene_relevant:
                errors.append(
                    f"{asset.role} is not confirmed relevant to smart-cabinet operations"
                )
            if not asset.sha256:
                errors.append(f"{asset.role} sha256 is required")
            if asset.reviewed_sha256 != asset.sha256:
                errors.append(f"{asset.role} review is not bound to current sha256")
            path = Path(asset.local_path)
            if not path.exists() or not path.is_file():
                errors.append(f"{asset.role} file is missing")
                continue
            content = path.read_bytes()
            if not content:
                errors.append(f"{asset.role} file is empty")
                continue
            digest = hashlib.sha256(content).hexdigest()
            if asset.sha256 and digest != asset.sha256:
                errors.append(f"{asset.role} hash mismatch")
            try:
                probe = self._probe(path)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                errors.append(f"{asset.role} probe failed: {exc}")
                continue
            if probe.mime != asset.mime:
                errors.append(
                    f"{asset.role} MIME mismatch: expected {asset.mime}, got {probe.mime}"
                )

            if asset.role == "short_video":
                if not _matches_aspect_ratio(
                    probe.width,
                    probe.height,
                    self._expected_video_aspect_ratio,
                ):
                    errors.append(
                        f"short_video aspect ratio is {probe.width}:{probe.height}, "
                        f"expected {self._expected_video_aspect_ratio}"
                    )
                tolerance = 3
                if abs(probe.duration_seconds - self._expected_video_duration_seconds) > tolerance:
                    errors.append(
                        f"short_video duration is {probe.duration_seconds:.1f}s, "
                        f"expected about {self._expected_video_duration_seconds}s"
                    )
        return errors


def probe_media(path: Path) -> MediaProbe:
    """Probe PNG directly and use ffprobe for MP4 metadata."""
    header = path.read_bytes()[:32]
    if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
        width, height = struct.unpack(">II", header[16:24])
        return MediaProbe(mime="image/png", width=width, height=height)

    if len(header) >= 12 and header[4:8] == b"ftyp":
        configured_executable = os.getenv("FFPROBE_PATH")
        if configured_executable and not Path(configured_executable).is_file():
            raise ValueError("FFPROBE_PATH does not point to a file")
        executable = configured_executable or shutil.which("ffprobe")
        if not executable:
            raise ValueError("ffprobe is required to validate generated video")
        completed = subprocess.run(
            [
                executable,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
        streams = payload.get("streams") or []
        if not streams:
            raise ValueError("video stream not found")
        stream = streams[0]
        return MediaProbe(
            mime="video/mp4",
            width=int(stream["width"]),
            height=int(stream["height"]),
            duration_seconds=float(payload.get("format", {}).get("duration", 0)),
        )

    raise ValueError("unsupported media format")


def _matches_aspect_ratio(width: int, height: int, expected: str) -> bool:
    try:
        expected_width, expected_height = (int(value) for value in expected.split(":", 1))
    except (TypeError, ValueError):
        return False
    if width <= 0 or height <= 0 or expected_width <= 0 or expected_height <= 0:
        return False
    actual = width / height
    target = expected_width / expected_height
    return abs(actual - target) / target <= 0.02
