"""PublisherFactory + BuilderContext.

Factory 负责组装 ChannelTarget，Registry 只管注册。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from publishing.registry import PublisherRegistry

if TYPE_CHECKING:
    from publishing.base import BaseCache, BaseMetrics
    from publishing.config import PublishConfig
    from publishing.manifest_repository import ManifestRepository
    from publishing.models import ChannelTarget


@dataclass
class BuilderContext:
    """Builder 统一入参（避免 **kwargs 持续膨胀）."""

    config: PublishConfig
    mode: str = "draft"
    manifest: ManifestRepository | None = None
    logger: logging.Logger | None = None
    cache: BaseCache | None = None  # 预留（Protocol / ABC）
    metrics: BaseMetrics | None = None  # 预留（Protocol / ABC）


class PublisherFactory:
    """根据 channel 组装 ChannelTarget."""

    @staticmethod
    def create(channel: str, builder_ctx: BuilderContext) -> ChannelTarget:
        """创建渠道目标."""
        builder = PublisherRegistry.get_builder(channel)
        return builder.build(builder_ctx)
