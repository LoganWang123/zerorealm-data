"""Normalize and assemble deterministic homepage media with FFmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def resolve_ffmpeg() -> str:
    """Resolve an explicitly configured FFmpeg binary or find it on PATH."""
    configured = os.getenv("FFMPEG_PATH")
    if configured:
        if not Path(configured).is_file():
            raise ValueError("FFMPEG_PATH does not point to a file")
        return configured
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("ffmpeg is required to assemble homepage media")
    return executable


def normalize_homepage_image(source: Path, output: Path) -> None:
    """Normalize a generated homepage image to an exact 1920x1080 PNG."""
    command = [
        resolve_ffmpeg(),
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-vf",
        "scale=1920:1080",
        "-frames:v",
        "1",
        "-f",
        "image2",
        str(output),
    ]
    _run_ffmpeg(command)


def assemble_homepage_video(
    clips: tuple[Path, Path, Path],
    output: Path,
) -> None:
    """Normalize and join three distinct five-second scenes without looping."""
    if len(clips) != 3:
        raise ValueError("Homepage video requires exactly three clips")

    command = [resolve_ffmpeg(), "-hide_banner", "-y"]
    for clip in clips:
        command.extend(["-i", str(clip)])

    scene_filters = []
    for index in range(3):
        scene_filters.append(
            f"[{index}:v]trim=duration=5,setpts=PTS-STARTPTS,"
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x071525,"
            f"fps=24,format=yuv420p[v{index}]"
        )
    filter_graph = ";".join(
        [
            *scene_filters,
            "[v0][v1]xfade=transition=fade:duration=0.25:offset=4.75[v01]",
            "[v01][v2]xfade=transition=fade:duration=0.25:offset=9.50[v]",
        ]
    )
    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-an",
            "-c:v",
            os.getenv("FFMPEG_VIDEO_ENCODER", "libx264"),
            "-b:v",
            "6M",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    _run_ffmpeg(command)


def _run_ffmpeg(command: list[str]) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError("ffmpeg failed to assemble homepage media") from exc
