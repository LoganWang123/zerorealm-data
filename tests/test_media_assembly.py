from pathlib import Path

import pytest

from publishing.media_generation.assembly import (
    assemble_homepage_video,
    normalize_homepage_image,
    resolve_ffmpeg,
)


def _fake_ffmpeg(tmp_path: Path, monkeypatch) -> Path:
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"binary")
    monkeypatch.setenv("FFMPEG_PATH", str(executable))
    return executable


def test_resolve_ffmpeg_prefers_explicit_existing_path(tmp_path, monkeypatch):
    executable = _fake_ffmpeg(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert resolve_ffmpeg() == str(executable)


def test_resolve_ffmpeg_rejects_invalid_explicit_path(tmp_path, monkeypatch):
    monkeypatch.setenv("FFMPEG_PATH", str(tmp_path / "missing.exe"))

    with pytest.raises(ValueError, match="FFMPEG_PATH"):
        resolve_ffmpeg()


def test_normalize_homepage_image_outputs_exact_png_contract(tmp_path, monkeypatch):
    executable = _fake_ffmpeg(tmp_path, monkeypatch)
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    output = tmp_path / "ready.png"
    calls = []
    monkeypatch.setattr(
        "publishing.media_generation.assembly.subprocess.run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    normalize_homepage_image(source, output)

    command, kwargs = calls[0]
    assert command[0] == str(executable)
    assert command[command.index("-vf") + 1] == "scale=1920:1080"
    assert command[-1] == str(output)
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 180


def test_assemble_homepage_video_uses_three_inputs_without_looping(
    tmp_path,
    monkeypatch,
):
    executable = _fake_ffmpeg(tmp_path, monkeypatch)
    clips = tuple(tmp_path / f"scene-{index}.mp4" for index in range(1, 4))
    for clip in clips:
        clip.write_bytes(b"video")
    output = tmp_path / "showcase.ready.mp4"
    calls = []
    monkeypatch.setattr(
        "publishing.media_generation.assembly.subprocess.run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    assemble_homepage_video(clips, output)

    command, kwargs = calls[0]
    filter_graph = command[command.index("-filter_complex") + 1]
    assert command[0] == str(executable)
    assert command.count("-i") == 3
    assert "-stream_loop" not in command
    assert filter_graph.count("xfade") == 2
    assert "scale=1920:1080:force_original_aspect_ratio=increase" in filter_graph
    assert "crop=1920:1080" in filter_graph
    assert "pad=" not in filter_graph
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[-1] == str(output)
    assert kwargs["check"] is True


def test_assemble_homepage_video_rejects_any_clip_count_other_than_three(
    tmp_path,
):
    output = tmp_path / "showcase.ready.mp4"

    with pytest.raises(ValueError, match="exactly three"):
        assemble_homepage_video((tmp_path / "only.mp4",), output)
