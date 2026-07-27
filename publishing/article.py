"""Article 统一内容模型.

定义 Article / ArticleMeta / Lifecycle 等领域对象。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class Lifecycle(Enum):
    """内容生命周期."""

    DRAFT = "draft"
    VALIDATED = "validated"
    RENDERED = "rendered"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class ArticleMeta:
    """Article 元数据."""

    uuid: str  # 确定性生成，幂等判断用
    slug: str  # "daily-2026-07-26"
    source: str  # "daily" / "insight" / "weekly" / "manual"
    issue: int  # 期号
    language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    created_at: str = ""  # ISO 8601
    updated_at: str = ""
    version: int = 1  # 内容模型版本号（迁移用）
    schema_version: int = 1  # Article 结构版本（Parser 迁移用）
    content_revision: int = 1  # 内容修订号（业务层）
    lifecycle: Lifecycle = Lifecycle.DRAFT


@dataclass
class ArticleItem:
    """单条新闻."""

    title: str
    excerpt: str
    source_url: str
    source_name: str


@dataclass
class ArticleSection:
    """新闻板块."""

    type: str  # industry / enterprise / ai_frontier / policy
    items: list[ArticleItem] = field(default_factory=list)


@dataclass
class Article:
    """统一内容模型."""

    metadata: ArticleMeta
    title: str  # "零域日报 No.1"
    date: str  # "2026-07-26"
    summary: list[str] = field(default_factory=list)  # 3 条要点
    sections: list[ArticleSection] = field(default_factory=list)
    cover: str = ""  # 封面图路径
    author: str = "ZeroRealm AI"
    tags: list[str] = field(default_factory=list)


def generate_uuid(source: str, date: str, issue: int) -> str:
    """确定性 UUID 生成（基于 source + date + issue）.

    同一篇日报无论解析多少次，UUID 始终一致，用于幂等判断。
    """
    raw = f"{source}:{date}:{issue}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
