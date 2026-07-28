"""Blocking media generation steps for the publication pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from publishing.media_generation.client import AgnesAPIError
from publishing.pipeline import PipelineContext, PipelineState, PipelineStep, StepResult, StepStatus

if TYPE_CHECKING:
    from publishing.media_generation.service import MediaGenerationService
    from publishing.media_generation.validation import MediaValidator


class GenerateMediaStep(PipelineStep):
    """Create the complete daily media set before rendering."""

    name = "generate_media"

    def __init__(self, service_factory: Callable[[], MediaGenerationService]):
        self._service_factory = service_factory

    def execute(self, ctx: PipelineContext) -> StepResult:
        if ctx.mode == "preview" or not ctx.config.media.enabled:
            return StepResult(
                status=StepStatus.SKIPPED,
                message="Media generation skipped",
            )
        try:
            bundle = self._service_factory().generate_daily(ctx.article)
        except AgnesAPIError as exc:
            return StepResult(
                status=StepStatus.FAILED,
                message=str(exc),
                retryable=exc.retryable,
            )
        except (OSError, ValueError) as exc:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Media generation failed: {exc}",
                retryable=False,
            )

        ctx.set(PipelineState.MEDIA_BUNDLE, bundle)
        ctx.article.cover = bundle.cover.local_path
        ctx.article.media_bundle = bundle
        return StepResult(status=StepStatus.SUCCESS, message="Media generated")


class ValidateMediaStep(PipelineStep):
    """Block publication unless every required generated asset is valid."""

    name = "validate_media"

    def __init__(self, validator: MediaValidator):
        self._validator = validator

    def execute(self, ctx: PipelineContext) -> StepResult:
        if ctx.mode == "preview" or not ctx.config.media.enabled:
            return StepResult(
                status=StepStatus.SKIPPED,
                message="Media validation skipped",
            )
        bundle = ctx.get(PipelineState.MEDIA_BUNDLE)
        errors = (
            ["Media bundle missing"]
            if bundle is None
            else self._validator.validate(bundle)
        )
        if errors:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Media validation failed: {'; '.join(errors)}",
            )
        return StepResult(status=StepStatus.SUCCESS, message="Media validation passed")
