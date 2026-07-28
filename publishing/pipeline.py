"""PublishPipeline — 纯执行器.

Step 序列由外部注入，Pipeline 本身零业务知识。
返回 PipelineContext，不耦合任何具体结果类型。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from publishing.models import PublishResult, PublishStatus

if TYPE_CHECKING:
    from publishing.article import Article
    from publishing.config import PublishConfig
    from publishing.manifest_repository import ManifestRepository
    from publishing.models import ChannelTarget, RenderContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# StepStatus / StepResult
# ---------------------------------------------------------------------------


class StepStatus(Enum):
    """Step 执行状态."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Step 执行结果."""

    status: StepStatus
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed: float = 0.0  # 耗时（秒）
    retryable: bool = False  # Pipeline 据此 + config.pipeline.retry 执行退避重试


# ---------------------------------------------------------------------------
# PipelineState (str, Enum)
# ---------------------------------------------------------------------------


class PipelineState(str, Enum):
    """Typed Key，避免字符串拼写错误，支持 IDE 自动补全."""

    RENDER_RESULT = "render_result"
    PUBLISH_RESULT = "publish_result"
    VALIDATION = "validation"
    WARNINGS = "warnings"
    STEP_RESULTS = "step_results"  # {step_name: StepResult}
    MEDIA_BUNDLE = "media_bundle"


# ---------------------------------------------------------------------------
# PipelineContext
# ---------------------------------------------------------------------------


@dataclass
class PipelineContext:
    """Context Object：所有 Step 共享的状态容器."""

    # 核心输入
    article: Article
    target: ChannelTarget
    render_context: RenderContext
    mode: str  # "draft" / "publish" / "preview" / "dry_run"
    trace_id: str  # 唯一 Trace 来源（Workflow 生命周期）

    # 基础设施
    config: PublishConfig
    manifest: ManifestRepository
    logger: logging.Logger

    # 状态容器（避免 Context 不断长字段）
    state: dict = field(default_factory=dict)

    # Typed Getter / Setter（Step 不直接操作 dict）
    def set(self, key: PipelineState, value: Any) -> None:
        self.state[key] = value

    def get(self, key: PipelineState, default: Any = None) -> Any:
        return self.state.get(key, default)


# ---------------------------------------------------------------------------
# PipelineStep (ABC)
# ---------------------------------------------------------------------------


from abc import ABC, abstractmethod  # noqa: E402


class PipelineStep(ABC):
    """Step 抽象基类."""

    name: str = "unnamed"

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> StepResult:
        """执行单一原子操作."""
        ...


# ---------------------------------------------------------------------------
# PublishPipeline
# ---------------------------------------------------------------------------


class PublishPipeline:
    """Step 序列由外部注入，Pipeline 本身零业务知识."""

    def __init__(self, steps: list[PipelineStep]):
        self.steps = steps

    # --- 生命周期 Hook（空实现，未来覆写） ---
    def before(self, ctx: PipelineContext) -> None:
        """Pipeline 执行前 Hook."""

    def after(self, ctx: PipelineContext) -> None:
        """Pipeline 执行后 Hook."""

    def rollback(self, ctx: PipelineContext, failed_step: str) -> None:
        """失败回滚 Hook."""

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """返回 Context 本身，不耦合任何具体结果类型."""
        self.before(ctx)
        step_results: dict[str, StepResult] = {}

        for step in self.steps:
            start = time.time()
            result = self._execute_with_retry(step, ctx)
            result.elapsed = time.time() - start
            step_results[step.name] = result

            ctx.logger.info(
                "step=%s status=%s elapsed=%.2fs",
                step.name,
                result.status.value,
                result.elapsed,
            )

            # 收集所有 Step 的 warnings（统一使用 typed getter/setter）
            if result.warnings:
                warnings = ctx.get(PipelineState.WARNINGS, [])
                warnings.extend(result.warnings)
                ctx.set(PipelineState.WARNINGS, warnings)

            if result.status == StepStatus.FAILED:
                ctx.set(
                    PipelineState.PUBLISH_RESULT,
                    PublishResult(
                        status=PublishStatus.FAILED,
                        channel=ctx.target.name,
                        failed_step=step.name,
                        message=result.message,
                    ),
                )
                self.rollback(ctx, step.name)
                break

        ctx.set(PipelineState.STEP_RESULTS, step_results)
        self.after(ctx)
        return ctx

    def _execute_with_retry(self, step: PipelineStep, ctx: PipelineContext) -> StepResult:
        """retryable + config.pipeline.retry_backoff 执行指数退避重试."""
        backoffs = ctx.config.pipeline.retry_backoff  # [1, 2, 4]
        result = step.execute(ctx)
        if result.status != StepStatus.FAILED or not result.retryable:
            return result

        ctx.logger.warning("step=%s failed, retrying with backoff=%s", step.name, backoffs)
        for delay in backoffs:
            time.sleep(delay)
            result = step.execute(ctx)
            if result.status != StepStatus.FAILED:
                return result
        return result
