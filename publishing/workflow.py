"""PublishWorkflow — 外层编排.

端到端编排：Parse → Pipeline(Steps) → Notify → Metrics。
Step 序列由 Workflow 定义，Pipeline 零业务知识。
"""

from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import TYPE_CHECKING

from publishing.parser import ArticleParser
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
    ):
        self.config = config
        self.manifest = manifest
        self.logger = logger or logging.getLogger("publishing.workflow")
        self.parser = ArticleParser()

    def run(
        self,
        article_path: str,
        target: ChannelTarget,
        context: RenderContext,
        mode: str = "draft",
    ) -> PublishResult:
        """执行完整发布流程."""
        # 1. Parse（含版本迁移）
        self.logger.info("Parsing: %s", article_path)
        article = self.parser.parse(article_path)
        self.logger.info(
            "Parsed: %s (uuid=%s, %d sections)",
            article.title,
            article.metadata.uuid,
            len(article.sections),
        )

        # 2. 组装 Pipeline（Step 序列由 Workflow 定义）
        steps = [ValidateStep(), RenderStep(), PublishStep(), RecordStep()]
        pipeline = PublishPipeline(steps=steps)

        # 3. 构建 Context
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

        # 4. 执行（Pipeline 返回 Context，不耦合具体结果类型）
        ctx = pipeline.run(ctx)

        # 5. Notify（预留）
        # 6. Metrics（预留）

        return ctx.get(PipelineState.PUBLISH_RESULT)
