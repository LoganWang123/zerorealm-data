"""共享数据模型.

RenderResult / RenderContext / PublishResult / MediaReference / UploadResult /
ValidationResult / ChannelMetadata / ChannelTarget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from publishing.asset_manager import AssetManager
    from publishing.base import BasePublisher, BaseRenderer
    from publishing.config import PublishConfig


# ---------------------------------------------------------------------------
# MediaReference
# ---------------------------------------------------------------------------


@dataclass
class MediaReference:
    """媒体引用."""

    local_path: str  # 本地路径
    remote_url: str = ""  # CDN URL（上传后填充）
    media_id: str = ""  # 渠道侧 ID（微信 media_id / OSS object key）
    sha256: str = ""  # 文件 hash
    mime: str = "image/png"
    width: int = 0
    height: int = 0
    role: str = ""


@dataclass
class MediaAsset:
    """Generated media with its role and provenance."""

    role: str
    local_path: str
    mime: str
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    sha256: str = ""
    prompt_version: str = "v1"
    model: str = ""
    remote_url: str = ""
    media_id: str = ""


@dataclass
class MediaBundle:
    """Complete set of media required by one daily publication."""

    cover: MediaAsset
    body_images: list[MediaAsset]
    video: MediaAsset | None = None

    def all_assets(self) -> list[MediaAsset]:
        return [self.cover, *self.body_images, *([self.video] if self.video else [])]


# ---------------------------------------------------------------------------
# UploadResult
# ---------------------------------------------------------------------------


@dataclass
class UploadResult:
    """上传统一返回值（适配 OSS / S3 / 微信 / 七牛）."""

    media_id: str  # 渠道侧 ID
    remote_url: str  # CDN URL
    expires_at: datetime | None = None  # 过期时间（临时素材用，永久为 None）


# ---------------------------------------------------------------------------
# ChannelMetadata（类型化）
# ---------------------------------------------------------------------------


@dataclass
class BaseChannelMetadata:
    """渠道元数据基类."""


@dataclass
class WechatMetadata(BaseChannelMetadata):
    """微信公众号渠道元数据."""

    copyright: str = "原创"
    need_open_comment: int = 0  # 0/1
    digest: str = ""


@dataclass
class WebsiteMetadata(BaseChannelMetadata):
    """官网渠道元数据."""

    canonical: str = ""
    slug: str = ""
    toc: bool = False


# ---------------------------------------------------------------------------
# RenderContext
# ---------------------------------------------------------------------------


@dataclass
class RenderContext:
    """渲染上下文.

    注：MediaStorage 属于 Renderer 内部依赖（DI），不放在 Context 中。
    注：trace_id 统一由 PipelineContext 持有，Renderer 通过 ctx.trace_id 获取。
    """

    config: PublishConfig
    asset_manager: AssetManager
    preview: bool = False
    environment: str = "dev"  # "dev" / "test" / "prod"
    theme: str = "default"  # 预留
    locale: str = "zh-CN"


# ---------------------------------------------------------------------------
# RenderResult
# ---------------------------------------------------------------------------


@dataclass
class RenderResult:
    """渲染产物."""

    # 跨渠道通用
    article_uuid: str  # 来源 Article 的确定性 UUID
    title: str
    body: str  # 最终 HTML
    summary: str  # 微信→digest / 网站→meta / RSS→description
    cover: MediaReference
    author: str
    char_count: int = 0  # 字符数（基于纯文本）
    word_count: int = 0  # 词数（基于纯文本）
    media: list[MediaReference] = field(default_factory=list)
    video: MediaReference | None = None

    # 渠道特有（类型安全）
    channel_metadata: BaseChannelMetadata = field(default_factory=BaseChannelMetadata)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """校验结果."""

    passed: bool
    errors: list[str] = field(default_factory=list)  # 阻断流程
    warnings: list[str] = field(default_factory=list)  # 不阻断，记录日志


# ---------------------------------------------------------------------------
# PublishResult
# ---------------------------------------------------------------------------


class PublishStatus(Enum):
    """发布状态."""

    SUCCESS = "success"  # 首次成功
    UPDATED = "updated"  # 更新已有（幂等）
    SKIPPED = "skipped"  # Pipeline 主动跳过（已发布/无变更/preview），不代表失败
    DRY_RUN = "dry_run"  # 演练
    FAILED = "failed"


@dataclass
class PublishResult:
    """发布结果."""

    status: PublishStatus
    channel: str
    draft_id: str | None = None
    publish_id: str | None = None
    url: str | None = None
    duration: float = 0.0
    message: str = ""
    raw_response: Mapping[str, Any] = field(default_factory=dict)
    failed_step: str | None = None  # 失败步骤名（resume 用）


# ---------------------------------------------------------------------------
# ChannelTarget
# ---------------------------------------------------------------------------


@dataclass
class ChannelTarget:
    """渠道目标（Renderer + Publisher 组合）."""

    name: str
    renderer: BaseRenderer
    publisher: BasePublisher
