"""Fetch original candidate URLs with HTML → Playwright fallback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from crawlers.base import RawItem
from crawlers.html_crawler import HTMLCrawler
from utils.helpers import generate_run_id

DEFAULT_MIN_CONTENT_CHARS = 80


@dataclass
class FetchResult:
    """Outcome of a discovery fetch attempt (HTML and/or Playwright)."""

    item: RawItem | None = None
    method: str = ""  # html | playwright | ""
    reason_codes: list[str] = field(default_factory=list)
    ok: bool = False


def content_is_sufficient(text: str, *, min_chars: int = DEFAULT_MIN_CONTENT_CHARS) -> bool:
    body = (text or "").strip()
    return len(body) >= min_chars


def _source_config(url: str, source_id: str, timeout: int, js_render: bool = False) -> dict:
    return {
        "id": source_id,
        "name": source_id,
        "url": url,
        "type": "web",
        "parser": "article",
        "timeout": timeout,
        "retry": 1,
        "js_render": js_render,
        "browser_headers": True,
        "extra_wait": 2000,
    }


def _annotate(item: RawItem, *, source_id: str, method: str) -> RawItem:
    provider = source_id.split(":", 1)[-1] if ":" in source_id else source_id
    item.metadata = {
        **(item.metadata or {}),
        "discovery_provider": provider,
        "discovery_fetch": True,
        "fetch_method": method,
    }
    return item


def fetch_html_article(
    url: str,
    *,
    source_id: str = "discovery:anysearch",
    run_id: str | None = None,
    timeout: int = 30,
) -> RawItem:
    rid = run_id or generate_run_id()
    crawler = HTMLCrawler(_source_config(url, source_id, timeout, js_render=False), rid)
    items = asyncio.run(crawler.fetch())
    if not items:
        raise ConnectionError(f"HTML extract returned no items for {url}")
    return _annotate(items[0], source_id=source_id, method="html")


def fetch_playwright_article(
    url: str,
    *,
    source_id: str = "discovery:anysearch",
    run_id: str | None = None,
    timeout: int = 30,
) -> RawItem:
    """Render with Playwright, then reuse HTMLCrawler article parsing."""
    rid = run_id or generate_run_id()
    html = asyncio.run(_playwright_get_html(url, timeout=timeout))
    crawler = HTMLCrawler(_source_config(url, source_id, timeout, js_render=True), rid)
    soup = BeautifulSoup(html, "lxml")
    items = crawler._parse_article_page(soup)
    if not items:
        raise ConnectionError(f"Playwright extract returned no items for {url}")
    return _annotate(items[0], source_id=source_id, method="playwright")


async def _playwright_get_html(url: str, *, timeout: int) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            page = await context.new_page()
            await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            return await page.content()
        finally:
            await browser.close()


def fetch_url_as_raw_item(
    url: str,
    *,
    source_id: str = "discovery:anysearch",
    run_id: str | None = None,
    timeout: int = 30,
    js_render: bool = False,
    min_chars: int = DEFAULT_MIN_CONTENT_CHARS,
    html_fetcher=None,
    playwright_fetcher=None,
) -> RawItem:
    """Backward-compatible helper returning RawItem or raising on total failure."""
    result = fetch_with_fallback(
        url,
        source_id=source_id,
        run_id=run_id,
        timeout=timeout,
        prefer_playwright=js_render,
        min_chars=min_chars,
        html_fetcher=html_fetcher,
        playwright_fetcher=playwright_fetcher,
    )
    if not result.ok or result.item is None:
        codes = ",".join(result.reason_codes) or "FETCH_FAILED"
        raise ConnectionError(f"Fetch failed for {url}: {codes}")
    return result.item


def fetch_with_fallback(
    url: str,
    *,
    source_id: str = "discovery:anysearch",
    run_id: str | None = None,
    timeout: int = 30,
    prefer_playwright: bool = False,
    min_chars: int = DEFAULT_MIN_CONTENT_CHARS,
    html_fetcher=None,
    playwright_fetcher=None,
) -> FetchResult:
    """HTML first; on empty/insufficient content, fallback to Playwright.

    Reason codes:
    - HTML_EMPTY / HTML_INSUFFICIENT → attempt Playwright
    - PLAYWRIGHT_FAILED → Playwright path failed
    - FETCH_FAILED → both paths failed
    """
    rid = run_id or generate_run_id()
    html_fn = html_fetcher or (
        lambda u: fetch_html_article(u, source_id=source_id, run_id=rid, timeout=timeout)
    )
    pw_fn = playwright_fetcher or (
        lambda u: fetch_playwright_article(u, source_id=source_id, run_id=rid, timeout=timeout)
    )
    reasons: list[str] = []

    if prefer_playwright:
        try:
            item = pw_fn(url)
            if content_is_sufficient(item.content_text, min_chars=min_chars):
                return FetchResult(item=item, method="playwright", reason_codes=[], ok=True)
            reasons.append("HTML_INSUFFICIENT" if (item.content_text or "").strip() else "HTML_EMPTY")
        except Exception:
            reasons.append("PLAYWRIGHT_FAILED")
            return FetchResult(item=None, method="", reason_codes=reasons + ["FETCH_FAILED"], ok=False)

    # HTML attempt
    html_item: RawItem | None = None
    try:
        html_item = html_fn(url)
        if content_is_sufficient(html_item.content_text, min_chars=min_chars):
            return FetchResult(item=html_item, method="html", reason_codes=[], ok=True)
        reasons.append(
            "HTML_INSUFFICIENT"
            if (html_item.content_text or "").strip()
            else "HTML_EMPTY"
        )
    except Exception:
        reasons.append("HTML_EMPTY")

    # Playwright fallback
    try:
        pw_item = pw_fn(url)
        if content_is_sufficient(pw_item.content_text, min_chars=min_chars):
            return FetchResult(item=pw_item, method="playwright", reason_codes=list(reasons), ok=True)
        reasons.append("PLAYWRIGHT_FAILED")
    except Exception:
        reasons.append("PLAYWRIGHT_FAILED")

    if "FETCH_FAILED" not in reasons:
        reasons.append("FETCH_FAILED")
    return FetchResult(item=None, method="", reason_codes=reasons, ok=False)
