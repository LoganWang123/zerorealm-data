"""Fetch original candidate URLs via existing HTML crawler patterns."""

from __future__ import annotations

from crawlers.base import RawItem
from crawlers.html_crawler import HTMLCrawler
from utils.helpers import generate_run_id


def fetch_url_as_raw_item(
    url: str,
    *,
    source_id: str = "discovery:anysearch",
    run_id: str | None = None,
    timeout: int = 30,
    js_render: bool = False,
) -> RawItem:
    """Fetch a single article URL and return one RawItem.

    Uses HTMLCrawler (article parser). Playwright/JS path is available when
    ``js_render=True`` for sites that need it.
    """
    rid = run_id or generate_run_id()
    config = {
        "id": source_id,
        "name": source_id,
        "url": url,
        "type": "web",
        "parser": "article",
        "timeout": timeout,
        "retry": 1,
        "js_render": js_render,
        "browser_headers": True,
    }
    if js_render:
        from crawlers.js_crawler import JSCrawler

        crawler: HTMLCrawler | JSCrawler = JSCrawler(config, rid)
    else:
        crawler = HTMLCrawler(config, rid)

    import asyncio

    items = asyncio.run(crawler.fetch())
    if not items:
        raise ConnectionError(f"No content extracted from {url}")
    item = items[0]
    item.metadata = {
        **(item.metadata or {}),
        "discovery_provider": source_id.split(":", 1)[-1] if ":" in source_id else source_id,
        "discovery_fetch": True,
    }
    return item
