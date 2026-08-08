"""Fetch original candidate URLs with HTML → Playwright fallback + diagnostics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from crawlers.base import RawItem
from crawlers.html_crawler import HTMLCrawler, _provenance_html_slice
from utils.helpers import generate_run_id

DEFAULT_MIN_CONTENT_CHARS = 80


@dataclass
class FetchResult:
    """Outcome of a discovery fetch attempt (HTML and/or Playwright)."""

    item: RawItem | None = None
    method: str = ""  # html | playwright | ""
    reason_codes: list[str] = field(default_factory=list)
    ok: bool = False
    http_status: int | None = None
    diagnostics: dict = field(default_factory=dict)


def content_is_sufficient(text: str, *, min_chars: int = DEFAULT_MIN_CONTENT_CHARS) -> bool:
    body = (text or "").strip()
    return len(body) >= min_chars


def classify_fetch_exception(exc: BaseException) -> list[str]:
    """Map transport/parser failures to detailed reason codes (no bypass)."""
    text = f"{type(exc).__name__}: {exc}".lower()
    codes: list[str] = []
    if "timeout" in text or "timed out" in text:
        codes.append("PLAYWRIGHT_TIMEOUT" if "playwright" in text else "HTTP_ERROR")
    if any(token in text for token in ("401", "403", "451", "blocked", "captcha", "access denied")):
        codes.append("BLOCKED")
    if any(token in text for token in ("robots", "forbidden", "unauthorized", "login required")):
        codes.append("ROBOTS_OR_ACCESS_RESTRICTED")
    if "404" in text or "410" in text:
        codes.append("HTTP_ERROR")
    if "http" in text or "connection" in text or "ssl" in text or "status" in text:
        if "HTTP_ERROR" not in codes:
            codes.append("HTTP_ERROR")
    if not codes:
        codes.append("HTTP_ERROR")
    return codes


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
    item = _annotate(items[0], source_id=source_id, method="playwright")
    item.content_html = _provenance_html_slice(soup)
    return item


async def _playwright_get_html(url: str, *, timeout: int) -> str:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
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
            try:
                response = await page.goto(
                    url, timeout=timeout * 1000, wait_until="domcontentloaded"
                )
            except PlaywrightTimeoutError as exc:
                raise TimeoutError(f"playwright timeout: {exc}") from exc
            status = response.status if response is not None else None
            if status in {401, 403, 451}:
                raise PermissionError(f"blocked http {status}")
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

    Reason codes (examples):
    - HTML_EMPTY / HTML_TOO_SHORT / JS_REQUIRED
    - PLAYWRIGHT_TIMEOUT / PLAYWRIGHT_EMPTY / PLAYWRIGHT_FAILED
    - HTTP_ERROR / BLOCKED / ROBOTS_OR_ACCESS_RESTRICTED
    - FETCH_FAILED (terminal)
    """
    rid = run_id or generate_run_id()
    html_fn = html_fetcher or (
        lambda u: fetch_html_article(u, source_id=source_id, run_id=rid, timeout=timeout)
    )
    pw_fn = playwright_fetcher or (
        lambda u: fetch_playwright_article(u, source_id=source_id, run_id=rid, timeout=timeout)
    )
    reasons: list[str] = []
    diagnostics: dict = {"url": url}

    def _body_code(item: RawItem | None) -> str:
        if item is None or not (item.content_text or "").strip():
            return "HTML_EMPTY"
        if not content_is_sufficient(item.content_text, min_chars=min_chars):
            return "HTML_TOO_SHORT"
        return ""

    if prefer_playwright:
        try:
            item = pw_fn(url)
            if content_is_sufficient(item.content_text, min_chars=min_chars):
                return FetchResult(item=item, method="playwright", reason_codes=[], ok=True)
            reasons.append("PLAYWRIGHT_EMPTY")
        except Exception as exc:
            reasons.extend(classify_fetch_exception(exc))
            if "PLAYWRIGHT_TIMEOUT" not in reasons and "timeout" in str(exc).lower():
                reasons.append("PLAYWRIGHT_TIMEOUT")
            reasons.append("PLAYWRIGHT_FAILED")
            return FetchResult(
                item=None,
                method="",
                reason_codes=list(dict.fromkeys(reasons + ["FETCH_FAILED"])),
                ok=False,
                diagnostics=diagnostics,
            )

    # HTML attempt
    try:
        html_item = html_fn(url)
        code = _body_code(html_item)
        if not code:
            return FetchResult(
                item=html_item,
                method="html",
                reason_codes=[],
                ok=True,
                http_status=html_item.http_status,
                diagnostics=diagnostics,
            )
        reasons.append(code)
        if code in {"HTML_EMPTY", "HTML_TOO_SHORT"}:
            reasons.append("JS_REQUIRED")
    except Exception as exc:
        reasons.extend(classify_fetch_exception(exc))
        reasons.append("HTML_EMPTY")

    # Playwright fallback
    try:
        pw_item = pw_fn(url)
        if content_is_sufficient(pw_item.content_text, min_chars=min_chars):
            return FetchResult(
                item=pw_item,
                method="playwright",
                reason_codes=list(dict.fromkeys(reasons)),
                ok=True,
                http_status=pw_item.http_status,
                diagnostics=diagnostics,
            )
        reasons.append("PLAYWRIGHT_EMPTY")
        reasons.append("PLAYWRIGHT_FAILED")
    except Exception as exc:
        reasons.extend(classify_fetch_exception(exc))
        if "timeout" in str(exc).lower() and "PLAYWRIGHT_TIMEOUT" not in reasons:
            reasons.append("PLAYWRIGHT_TIMEOUT")
        reasons.append("PLAYWRIGHT_FAILED")

    if "FETCH_FAILED" not in reasons:
        reasons.append("FETCH_FAILED")
    return FetchResult(
        item=None,
        method="",
        reason_codes=list(dict.fromkeys(reasons)),
        ok=False,
        diagnostics=diagnostics,
    )
