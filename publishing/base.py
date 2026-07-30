"""抽象基类.

BaseRenderer / BasePublisher / BaseMediaStorage / BaseCache / BaseMetrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from publishing.article import Article
    from publishing.models import (
        MediaReference,
        PublishResult,
        RenderContext,
        RenderResult,
        UploadResult,
    )


class BaseRenderer(ABC):
    """Renderer 抽象：Article + RenderContext → RenderResult."""

    @abstractmethod
    def render(self, article: Article, context: RenderContext) -> RenderResult:
        """渲染文章为渠道产物."""
        ...


class BasePublisher(ABC):
    """Publisher 抽象：RenderResult → API → PublishResult."""

    @abstractmethod
    def publish(
        self,
        result: RenderResult,
        dry_run: bool = False,
        publish_now: bool = False,
        notify_followers: bool = False,
    ) -> PublishResult:
        """发布渲染产物到渠道."""
        ...


class BaseMediaStorage(ABC):
    """MediaStorage 抽象：文件 → UploadResult."""

    @abstractmethod
    def upload(self, ref: MediaReference) -> UploadResult:
        """上传媒体文件，返回统一结果."""
        ...


class BaseCache(ABC):
    """缓存抽象（Protocol / ABC）.

    未来可对接 Redis / DiskCache / MemoryCache。
    """

    @abstractmethod
    def get(self, key: str) -> dict | None:
        ...

    @abstractmethod
    def set(self, key: str, value: dict, ttl: int | None = None) -> None:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...


class BaseMetrics(ABC):
    """指标收集抽象（Protocol / ABC）."""

    @abstractmethod
    def record(self, name: str, value: float, tags: dict | None = None) -> None:
        ...
