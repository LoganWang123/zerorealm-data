"""PublishWorkflow — 外层编排.

端到端编排：Parse → Pipeline(Steps) → Notify → Metrics。
Step 序列由 Workflow 定义，Pipeline 零业务知识。
"""

from __future__ import annotations

import logging
import os
import uuid as uuid_mod
from typing import TYPE_CHECKING

from publishing.parser import ArticleParser
from publishing.media_generation.errors import (
    AgnesImageGenerationDisabled,
    LocalImageGeneratorUnavailable,
)
from publishing.media_generation.providers import build_default_image_provider
from publishing.media_generation.service import MediaGenerationService
from publishing.media_generation.steps import GenerateMediaStep, ValidateMediaStep
from publishing.media_generation.validation import MediaValidator
from publishing.pipeline import PipelineContext, PipelineState, PublishPipeline
from publishing.steps import PublishStep, RecordStep, RenderStep, ValidateStep

if TYPE_CHECKING:
    from publishing.config import PublishConfig
    from publishing.manifest_repository import ManifestRepository
    from publishing.models import ChannelTarget, PublishResult, RenderContext


def generate_trace_id() -> str:
    """生成 Trace ID."""
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    short = uuid_mod.uuid4().hex[:6]
    return f"pub-{ts}-{short}"


class PublishWorkflow:
    """发布工作流（外层编排）."""

    def __init__(
        self,
        config: PublishConfig,
        manifest: ManifestRepository,
        logger: logging.Logger | None = None,
        media_service_factory=None,
        media_validator: MediaValidator | None = None,
    ):
        self.config = config
        self.manifest = manifest
        self.logger = logger or logging.getLogger("publishing.workflow")
        self.parser = ArticleParser()
        self._media_service_factory = media_service_factory or self._build_media_service
        self._media_validator = media_validator or MediaValidator(
            expected_body_images=config.media.body_image_count,
            expected_video_aspect_ratio=config.media.video_aspect_ratio,
            expected_video_duration_seconds=config.media.video_duration_seconds,
        )

    def build_steps(self):
        """Build the ordered, channel-agnostic publication steps."""
        return [
            ValidateStep(),
            GenerateMediaStep(self._media_service_factory),
            ValidateMediaStep(self._media_validator),
            RenderStep(),
            PublishStep(),
            RecordStep(),
        ]

    def _build_media_service(self) -> MediaGenerationService:
        """Build local-only media service. Never constructs AgnesClient."""
        # Explicit guard: even if AGNES_API_KEY is present, production must not use it.
        if os.getenv("ZEROREALM_FORCE_AGNES_IMAGE", "").strip() in {"1", "true", "yes"}:
            raise AgnesImageGenerationDisabled(
                "ZEROREALM_FORCE_AGNES_IMAGE is rejected; Agnes image generation is disabled"
            )
        provider_name = getattr(self.config.media, "provider", "local") or "local"
        allow_programmatic = getattr(self.config.media, "allow_programmatic", True)
        try:
            client = build_default_image_provider(
                provider_name=provider_name,
                image_model=os.getenv(
                    "ZEROREALM_LOCAL_IMAGE_MODEL",
                    self.config.media.image_model,
                ),
                allow_programmatic=allow_programmatic,
            )
        except (AgnesImageGenerationDisabled, LocalImageGeneratorUnavailable):
            raise
        return MediaGenerationService(client=client, config=self.config.media)

    def run(
        self,
        article_path: str,
        target: ChannelTarget,
        context: RenderContext,
        mode: str = "draft",
    ) -> PublishResult:
        """Parse an article path and publish via ``run_article`` (backward compatible)."""
        self.logger.info("Parsing: %s", article_path)
        article = self.parser.parse(article_path)
        self.logger.info(
            "Parsed: %s (uuid=%s, %d sections)",
            article.title,
            article.metadata.uuid,
            len(article.sections),
        )
        return self.run_article(article, target, context, mode=mode)

    def run_article(
        self,
        article,
        target: ChannelTarget,
        context: RenderContext,
        mode: str = "draft",
    ) -> PublishResult:
        """Publish an in-memory Article through the existing step pipeline."""
        steps = self.build_steps()
        pipeline = PublishPipeline(steps=steps)
        ctx = PipelineContext(
            article=article,
            target=target,
            render_context=context,
            mode=mode,
            trace_id=generate_trace_id(),
            config=self.config,
            manifest=self.manifest,
            logger=self.logger,
        )
        ctx = pipeline.run(ctx)
        return ctx.get(PipelineState.PUBLISH_RESULT)
