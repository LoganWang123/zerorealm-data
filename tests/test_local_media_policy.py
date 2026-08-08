"""Local-only / IDE MediaJob policy: Agnes production invocations must stay at zero."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from publishing.article import Article, ArticleMeta
from publishing.config import MediaConfig, PublishConfig
from publishing.media_generation.errors import (
    AgnesImageGenerationDisabled,
    PendingLocalGeneration,
)
from publishing.media_generation.media_job import (
    attach_image,
    can_publish,
    create_job,
    set_review_status,
)
from publishing.media_generation.prompt_package import write_prompt_package, build_brief_for_article
from publishing.media_generation.providers import (
    DisabledAgnesImageGenerator,
    LocalImageGenerator,
    build_default_image_provider,
)
from publishing.media_generation.service import MediaGenerationService
from publishing.workflow import PublishWorkflow


class TrackingAgnes:
    image_model = "agnes-should-not-run"
    video_model = "agnes-should-not-run"

    def __init__(self):
        self.image_calls = 0
        self.video_calls = 0

    def generate_image(self, prompt, size):
        self.image_calls += 1
        return b"bad"

    def generate_video(self, *args, **kwargs):
        self.video_calls += 1
        return b"bad"


def test_default_provider_is_local_not_agnes():
    provider = build_default_image_provider(
        provider_name="local",
        image_model="local-programmatic",
    )
    assert isinstance(provider, LocalImageGenerator)


def test_agnes_provider_name_is_rejected():
    with pytest.raises(AgnesImageGenerationDisabled):
        build_default_image_provider(provider_name="agnes", image_model="x")


def test_workflow_factory_never_constructs_agnes(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "should-not-be-used-for-images")
    monkeypatch.delenv("ZEROREALM_FORCE_AGNES_IMAGE", raising=False)
    config = PublishConfig()
    config.media.provider = "local"
    workflow = PublishWorkflow(config=config, manifest=object())  # type: ignore[arg-type]
    service = workflow._build_media_service()
    assert isinstance(service._client, LocalImageGenerator)


def test_force_agnes_env_is_rejected(monkeypatch):
    monkeypatch.setenv("ZEROREALM_FORCE_AGNES_IMAGE", "1")
    workflow = PublishWorkflow(config=PublishConfig(), manifest=object())  # type: ignore[arg-type]
    with pytest.raises(AgnesImageGenerationDisabled):
        workflow._build_media_service()


def test_daily_scene_images_create_media_jobs_without_agnes(tmp_path, monkeypatch):
    tracker = TrackingAgnes()
    monkeypatch.chdir(tmp_path)
    local = LocalImageGenerator(allow_programmatic=True, call_counter=[])
    service = MediaGenerationService(
        client=local,
        config=MediaConfig(video_enabled=False, body_image_count=3),
        output_root=tmp_path / "generated",
        curated_cover_root=tmp_path / "covers",
        media_jobs_root=tmp_path / "jobs",
    )
    article = Article(
        metadata=ArticleMeta(uuid="u1", slug="daily-2026-08-07", source="daily", issue=1),
        title="智能柜补货效率观察",
        date="2026-08-07",
        summary=["摘要"],
    )
    with pytest.raises(PendingLocalGeneration) as exc:
        service.generate_daily(article)
    assert tracker.image_calls == 0
    assert "PENDING_LOCAL_GENERATION" in str(exc.value)
    jobs = list((tmp_path / "jobs").glob("*/**/job.json"))
    assert len(jobs) >= 3


def test_disabled_agnes_guard_blocks_calls():
    client = DisabledAgnesImageGenerator()
    with pytest.raises(AgnesImageGenerationDisabled):
        client.generate_image("x", "1280x720")


def test_media_job_attach_validate_and_publish_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = create_job(
        content_id="e2e-brief",
        channel="website",
        purpose="illustration",
        title="测试场景",
        width=1280,
        height=720,
        root=tmp_path / "jobs",
    )
    image_path = tmp_path / "scene.png"
    Image.new("RGB", (1280, 720), (40, 50, 60)).save(image_path)
    attached = attach_image(
        job.id,
        image_path,
        generator_agent="cursor",
        generator_type="ide_native",
        root=tmp_path / "jobs",
    )
    assert attached.status == "pending_review"
    assert can_publish(attached) is False
    # generatorAgent must not affect gate
    attached.generatorAgent = "codex"
    assert can_publish(attached) is False
    approved = set_review_status(job.id, "approved", root=tmp_path / "jobs")
    assert can_publish(approved) is True
    rejected = set_review_status(job.id, "rejected", root=tmp_path / "jobs")
    assert can_publish(rejected) is False


def test_media_job_rejects_corrupt_and_unsafe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = create_job(
        content_id="bad",
        purpose="illustration",
        width=1280,
        height=720,
        root=tmp_path / "jobs",
    )
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not-an-image")
    with pytest.raises(ValueError):
        attach_image(job.id, bad, root=tmp_path / "jobs")


def test_write_prompt_package_shape(tmp_path):
    brief = build_brief_for_article(
        content_id="demo",
        channel="website",
        purpose="og",
        title="缺货率",
        width=1200,
        height=630,
        aspect_ratio="1.91:1",
    )
    job = write_prompt_package(brief, tmp_path)
    assert (job / "prompt.zh-CN.txt").is_file()
