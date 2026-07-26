"""Base crawler abstract class."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from utils.logger import get_logger
from utils.helpers import generate_id, now_iso


@dataclass
class RawItem:
    """Standardized raw data item."""

    id: str
    source: str
    source_type: str
    language: str
    title: str
    url: str
    published_at: str
    crawled_at: str
    run_id: str
    crawl_status: str
    http_status: int
    content_html: str
    content_text: str
    summary: str
    author: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "source_type": self.source_type,
            "language": self.language,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "crawled_at": self.crawled_at,
            "run_id": self.run_id,
            "crawl_status": self.crawl_status,
            "http_status": self.http_status,
            "content_html": self.content_html,
            "content_text": self.content_text,
            "summary": self.summary,
            "author": self.author,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class BaseCrawler(ABC):
    """Abstract base crawler with retry logic."""

    def __init__(self, source_config: dict, run_id: str):
        self.source_id: str = source_config["id"]
        self.name: str = source_config.get("name", self.source_id)
        self.url: str = source_config["url"]
        self.source_type: str = source_config.get("type", "web")
        self.category: str = source_config.get("category", "news")
        self.score: int = source_config.get("score", 80)
        self.retry: int = source_config.get("retry", 3)
        self.timeout: int = source_config.get("timeout", 30)
        self.user_agent: str = source_config.get("user_agent", "zerorealm-bot/1.0")
        self.run_id = run_id
        self.logger = get_logger()

    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        """Fetch raw data from source. Must be implemented by subclass."""
        ...

    async def run(self) -> list[RawItem]:
        """Execute crawl with exponential backoff retry."""
        for attempt in range(self.retry):
            try:
                self.logger.info(f"[{self.source_id}] Fetching {self.url}")
                items = await self.fetch()
                self.logger.info(f"[{self.source_id}] Got {len(items)} items")
                return items
            except Exception as e:
                wait = 30 * (2**attempt)  # 30s, 60s, 120s
                self.logger.warning(
                    f"[{self.source_id}] Attempt {attempt + 1}/{self.retry} failed: {e}, "
                    f"retry in {wait}s"
                )
                if attempt < self.retry - 1:
                    await asyncio.sleep(wait)

        self.logger.error(f"[{self.source_id}] All {self.retry} attempts failed")
        return []

    def _make_item(
        self,
        title: str,
        url: str,
        content_html: str = "",
        content_text: str = "",
        summary: str = "",
        author: str = "",
        published_at: str = "",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> RawItem:
        """Helper to create a RawItem with auto-generated fields."""
        return RawItem(
            id=generate_id(self.source_id, url),
            source=self.source_id,
            source_type=self.source_type,
            language="zh-CN",
            title=title,
            url=url,
            published_at=published_at or now_iso(),
            crawled_at=now_iso(),
            run_id=self.run_id,
            crawl_status="success",
            http_status=200,
            content_html=content_html,
            content_text=content_text,
            summary=summary,
            author=author,
            tags=tags or [],
            metadata={
                "category": self.category,
                "score": self.score,
                **(metadata or {}),
            },
        )
