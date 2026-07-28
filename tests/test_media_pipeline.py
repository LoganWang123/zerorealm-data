import logging

from publishing.article import Article, ArticleMeta
from publishing.asset_manager import AssetManager
from publishing.config import PublishConfig
from publishing.media_generation.client import AgnesAPIError
from publishing.media_generation.steps import GenerateMediaStep, ValidateMediaStep
from publishing.models import (
    ChannelTarget,
    MediaAsset,
    MediaBundle,
    PublishResult,
    PublishStatus,
    RenderContext,
    RenderResult,
)
from publishing.pipeline import PipelineContext, PipelineState, PublishPipeline, StepStatus
from publishing.steps import PublishStep, RenderStep
from publishing.workflow import PublishWorkflow


def article():
    return Article(
        metadata=ArticleMeta(
            uuid="article-1",
            slug="daily-2026-07-29",
            source="daily",
            issue=4,
        ),
        title="零域日报",
        date="2026-07-29",
        summary=["summary"],
    )


def bundle():
    return MediaBundle(
        cover=MediaAsset("cover", "cover.png", "image/png"),
        body_images=[
            MediaAsset(f"body_{index}", f"body-{index}.png", "image/png")
            for index in range(1, 4)
        ],
        video=MediaAsset("short_video", "short.mp4", "video/mp4"),
    )


class FakeManifest:
    def save(self, **kwargs):
        return None

    def mark_failed(self, *args):
        return None


class CountingRenderer:
    def __init__(self):
        self.calls = 0

    def render(self, current_article, context):
        self.calls += 1
        return RenderResult(
            article_uuid=current_article.metadata.uuid,
            title=current_article.title,
            body="<p>body</p>",
            summary="summary",
            cover=MediaAsset("cover", "cover.png", "image/png"),
            author=current_article.author,
        )


class CountingPublisher:
    def __init__(self):
        self.calls = 0

    def publish(self, result, dry_run=False, publish_now=False):
        self.calls += 1
        return PublishResult(status=PublishStatus.SUCCESS, channel="wechat")


def pipeline_context(mode="draft"):
    config = PublishConfig()
    renderer = CountingRenderer()
    publisher = CountingPublisher()
    target = ChannelTarget(name="wechat", renderer=renderer, publisher=publisher)
    context = PipelineContext(
        article=article(),
        target=target,
        render_context=RenderContext(config=config, asset_manager=AssetManager()),
        mode=mode,
        trace_id="trace-1",
        config=config,
        manifest=FakeManifest(),
        logger=logging.getLogger("test.media-pipeline"),
    )
    return context, renderer, publisher


def test_workflow_places_media_steps_between_validation_and_rendering():
    workflow = PublishWorkflow(
        config=PublishConfig(),
        manifest=FakeManifest(),
        media_service_factory=lambda: None,
    )

    assert [step.name for step in workflow.build_steps()] == [
        "validate",
        "generate_media",
        "validate_media",
        "render",
        "publish",
        "record",
    ]


def test_generation_failure_prevents_rendering_and_publishing():
    class FailingService:
        def generate_daily(self, current_article):
            raise AgnesAPIError("Agnes unavailable", retryable=False)

    context, renderer, publisher = pipeline_context()
    pipeline = PublishPipeline(
        [
            GenerateMediaStep(lambda: FailingService()),
            RenderStep(),
            PublishStep(),
        ]
    )

    result_context = pipeline.run(context)

    result = result_context.get(PipelineState.PUBLISH_RESULT)
    assert result.status == PublishStatus.FAILED
    assert result.failed_step == "generate_media"
    assert renderer.calls == 0
    assert publisher.calls == 0


def test_preview_skips_provider_factory():
    calls = []
    context, _, _ = pipeline_context(mode="preview")
    step = GenerateMediaStep(lambda: calls.append("created"))

    result = step.execute(context)

    assert result.status == StepStatus.SKIPPED
    assert calls == []


def test_dry_run_generates_and_validates_media_without_publishing():
    class Service:
        def generate_daily(self, current_article):
            return bundle()

    class Validator:
        def validate(self, current_bundle):
            return []

    context, _, publisher = pipeline_context(mode="dry_run")
    pipeline = PublishPipeline(
        [
            GenerateMediaStep(lambda: Service()),
            ValidateMediaStep(Validator()),
        ]
    )

    result_context = pipeline.run(context)

    assert result_context.get(PipelineState.MEDIA_BUNDLE) is not None
    assert publisher.calls == 0
