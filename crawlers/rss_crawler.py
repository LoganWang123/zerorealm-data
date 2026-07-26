"""RSS feed crawler using feedparser."""

import feedparser
from dateutil import parser as date_parser

from crawlers.base import BaseCrawler, RawItem
from utils.helpers import now_iso


class RSSCrawler(BaseCrawler):
    """Crawler for RSS/Atom feeds."""

    async def fetch(self) -> list[RawItem]:
        """Parse RSS feed and return list of RawItems."""
        feed = feedparser.parse(
            self.url,
            request_headers={"User-Agent": self.user_agent},
        )

        if feed.bozo and not feed.entries:
            raise ConnectionError(
                f"Feed parse error: {feed.bozo_exception}"
            )

        items = []
        for entry in feed.entries:
            # Extract published time
            published_at = ""
            if hasattr(entry, "published"):
                try:
                    dt = date_parser.parse(entry.published)
                    published_at = dt.isoformat(timespec="seconds")
                except (ValueError, TypeError):
                    published_at = now_iso()
            elif hasattr(entry, "updated"):
                try:
                    dt = date_parser.parse(entry.updated)
                    published_at = dt.isoformat(timespec="seconds")
                except (ValueError, TypeError):
                    published_at = now_iso()

            # Extract content
            content_html = ""
            content_text = ""
            if hasattr(entry, "content") and entry.content:
                content_html = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                content_html = entry.get("summary", "")

            # Summary
            summary = entry.get("summary", "")
            if len(summary) > 500:
                summary = summary[:500] + "..."

            # Tags from RSS categories
            tags = []
            if hasattr(entry, "tags") and entry.tags:
                tags = [t.get("term", "") for t in entry.tags if t.get("term")]

            # Author
            author = entry.get("author", "")

            item = self._make_item(
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                content_html=content_html,
                content_text=content_text,
                summary=summary,
                author=author,
                published_at=published_at,
                tags=tags,
                metadata={"feed_title": feed.feed.get("title", "")},
            )
            items.append(item)

        return items
