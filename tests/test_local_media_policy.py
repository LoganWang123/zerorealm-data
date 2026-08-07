"""Local-only media policy: Agnes production invocations must stay at zero."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from publishing.article import Article, ArticleMeta
from publishing.config import MediaConfig, PublishConfig
from publishing.media_generation.errors import AgnesImageGenerationDisabled
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


def test_workflow_factory_never_constructs_agnes(monkeypatch, tmp_path):
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


def test_local_generation_agnes_call_count_is_zero(tmp_path):
    tracker = TrackingAgnes()
    # Production path uses LocalImageGenerator; tracker must remain untouched.
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
    bundle = service.generate_daily(article)
    assert tracker.image_calls == 0
    assert tracker.video_calls == 0
    assert Path(bundle.cover.local_path).is_file()
    assert len(bundle.body_images) == 3


def test_disabled_agnes_guard_blocks_calls():
    client = DisabledAgnesImageGenerator()
    with pytest.raises(AgnesImageGenerationDisabled):
        client.generate_image("x", "1280x720")


def test_prompt_only_package_when_programmatic_disabled(tmp_path):
    local = LocalImageGenerator(allow_programmatic=False)
    service = MediaGenerationService(
        client=local,
        config=MediaConfig(video_enabled=False, allow_programmatic=False),
        output_root=tmp_path / "generated",
        curated_cover_root=tmp_path / "covers",
        media_jobs_root=tmp_path / "jobs",
    )
    article = Article(
        metadata=ArticleMeta(uuid="u2", slug="brief-demo", source="research", issue=0),
        title="案例封面",
        date="2026-08-07",
        summary=[],
    )
    from publishing.media_generation.errors import PendingLocalGeneration

    with pytest.raises(PendingLocalGeneration):
        service.generate_daily(article)
    jobs = list((tmp_path / "jobs").glob("**/metadata.json"))
    assert jobs
    meta = json.loads(jobs[0].read_text(encoding="utf-8"))
    assert meta["status"] == "pending_local_generation"


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
    assert (job / "prompt.en.txt").is_file()
    assert (job / "negative-prompt.txt").is_file()
    assert (job / "image-brief.json").is_file()
