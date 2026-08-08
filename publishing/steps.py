"""Pipeline Step 实现.

ValidateStep / RenderStep / PublishStep / RecordStep.
每个 Step 只做一件事。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from publishing.pipeline import PipelineContext, PipelineState, PipelineStep, StepResult, StepStatus
from publishing.models import PublishStatus

if TYPE_CHECKING:
    from publishing.models import PublishResult


class ValidateStep(PipelineStep):
    """校验 Article 完整性."""

    name = "validate"

    def execute(self, ctx: PipelineContext) -> StepResult:
        from publishing.validator import ArticleValidator

        validator = ArticleValidator()
        result = validator.validate(ctx.article)

        ctx.set(PipelineState.VALIDATION, result)

        if not result.passed:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Validation failed: {'; '.join(result.errors)}",
            )

        return StepResult(
            status=StepStatus.SUCCESS,
            message="Validation passed",
            warnings=result.warnings,
        )


class EditorialGateStep(PipelineStep):
    """Production Editorial Hard Gate — runs BEFORE rendering/publishing.

    Only applies to Daily-sourced articles that carry the original raw
    frontmatter (``Article.raw``, populated by :class:`publishing.parser.ArticleParser`).
    Programmatically-built Article instances (``raw`` defaults to ``{}``) and
    non-daily sources (research/case/etc.) are left untouched.

    A failed hard gate blocks the shared pipeline for BOTH the website and
    WeChat channels (they run the same step sequence), unless a signed-off
    ``editorial_exception`` is present and none of the failing codes are in
    ``editorial_gate.NON_BYPASSABLE_ERROR_CODES``. A bare ``manual_reviewed``
    flag never bypasses a hard failure on its own.
    """

    name = "editorial_gate"

    def execute(self, ctx: PipelineContext) -> StepResult:
        from publishing.editorial_gate import is_bypass_allowed, run_daily_editorial_gate

        article = ctx.article
        source = getattr(getattr(article, "metadata", None), "source", "") or ""
        raw = getattr(article, "raw", None) or {}
        if source != "daily" or not raw:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="Editorial gate skipped: not a daily source payload",
            )

        result = run_daily_editorial_gate(raw)
        ctx.set(PipelineState.EDITORIAL_GATE_RESULT, result)

        if result.passed:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="Editorial gate passed",
                warnings=[str(w) for w in result.warnings],
            )

        codes = ", ".join(sorted(set(result.error_codes)))
        if is_bypass_allowed(raw, result):
            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Editorial gate failed ({codes}) but bypassed via editorial_exception",
                warnings=[str(e) for e in result.errors],
            )

        return StepResult(
            status=StepStatus.FAILED,
            message=f"Editorial gate failed: {codes}",
        )


class RenderStep(PipelineStep):
    """渲染 Article → RenderResult."""

    name = "render"

    def execute(self, ctx: PipelineContext) -> StepResult:
        try:
            render_result = ctx.target.renderer.render(ctx.article, ctx.render_context)
            ctx.set(PipelineState.RENDER_RESULT, render_result)
            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Rendered: {render_result.char_count} chars",
            )
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Render failed: {e}",
                retryable=False,
            )


class PublishStep(PipelineStep):
    """发布 RenderResult → 渠道 API."""

    name = "publish"

    def execute(self, ctx: PipelineContext) -> StepResult:
        render_result = ctx.get(PipelineState.RENDER_RESULT)
        if render_result is None:
            return StepResult(
                status=StepStatus.FAILED,
                message="No render result found",
            )

        # preview 模式：跳过实际发布
        if ctx.mode == "preview":
            ctx.set(
                PipelineState.PUBLISH_RESULT,
                _preview_result(ctx, render_result),
            )
            return StepResult(status=StepStatus.SKIPPED, message="Preview mode, skipped")

        # dry_run 模式
        dry_run = ctx.mode == "dry_run"

        try:
            result = ctx.target.publisher.publish(
                render_result,
                dry_run=dry_run,
                publish_now=ctx.mode == "publish",
                notify_followers=ctx.mode == "notify",
            )
            ctx.set(PipelineState.PUBLISH_RESULT, result)

            if result.status == PublishStatus.FAILED:
                return StepResult(
                    status=StepStatus.FAILED,
                    message=result.message,
                    retryable=True,
                )

            return StepResult(
                status=StepStatus.SUCCESS,
                message=f"Published: {result.status.value}",
            )
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Publish error: {e}",
                retryable=True,
            )


class RecordStep(PipelineStep):
    """记录发布结果到 Manifest."""

    name = "record"

    def execute(self, ctx: PipelineContext) -> StepResult:
        publish_result = ctx.get(PipelineState.PUBLISH_RESULT)
        if publish_result is None:
            return StepResult(status=StepStatus.SKIPPED, message="No publish result")

        # 只有成功/更新才记录
        if publish_result.status in (PublishStatus.SUCCESS, PublishStatus.UPDATED):
            ctx.manifest.save(
                article_uuid=ctx.article.metadata.uuid,
                channel=ctx.target.name,
                result=publish_result,
            )
            if publish_result.publish_id:
                ctx.manifest.mark_published(ctx.article.metadata.uuid, ctx.target.name)
            return StepResult(status=StepStatus.SUCCESS, message="Recorded to manifest")

        if publish_result.status == PublishStatus.FAILED:
            ctx.manifest.mark_failed(
                ctx.article.metadata.uuid,
                ctx.target.name,
                publish_result.failed_step or "unknown",
            )

        return StepResult(status=StepStatus.SUCCESS, message="Record step done")


def _preview_result(ctx: PipelineContext, render_result) -> "PublishResult":
    """Preview 模式生成预览文件."""
    from pathlib import Path

    from publishing.models import PublishResult

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{ctx.article.metadata.slug}.html"
    output_path.write_text(render_result.body, encoding="utf-8")

    ctx.logger.info("Preview saved: %s", output_path)

    return PublishResult(
        status=PublishStatus.DRY_RUN,
        channel=ctx.target.name,
        message=f"Preview saved to {output_path}",
    )
