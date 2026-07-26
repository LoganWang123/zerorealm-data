"""JS-rendered web crawler using Playwright for SPA pages."""

import asyncio
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, RawItem
from utils.logger import get_logger


class JSCrawler(BaseCrawler):
    """Crawler for JavaScript-rendered pages (SPAs) using Playwright."""

    def __init__(self, source_config: dict, run_id: str):
        super().__init__(source_config, run_id)
        # Source-specific CSS selectors (can be overridden in sources.yaml)
        self.selectors = source_config.get("selectors", {})
        # Extra wait time for slow SPAs (ms)
        self.extra_wait = source_config.get("extra_wait", 3000)
        # Whether to ignore HTTPS errors in browser
        self.ignore_https_errors = not source_config.get("ssl_verify", True)

    async def fetch(self) -> list[RawItem]:
        """Fetch page with JS rendering and parse links."""
        from playwright.async_api import async_playwright

        logger = get_logger()
        logger.debug(f"[{self.source_id}] Launching browser...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                locale="zh-CN",
                ignore_https_errors=self.ignore_https_errors,
            )
            page = await context.new_page()

            try:
                await page.goto(self.url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
                # Wait for network to settle
                await page.wait_for_timeout(self.extra_wait)
                # Scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                html = await page.content()
            finally:
                await browser.close()

        soup = BeautifulSoup(html, "lxml")
        return self._parse_list_page(soup)

    def _parse_list_page(self, soup: BeautifulSoup) -> list[RawItem]:
        """Parse a JS-rendered page for article links."""
        items = []
        seen_urls = set()

        # Use configured selectors if available
        container_selector = self.selectors.get("container")
        link_selector = self.selectors.get("links", "a")
        title_selector = self.selectors.get("title")

        if container_selector:
            containers = soup.select(container_selector)
        else:
            containers = [soup]

        for container in containers:
            if link_selector != "a":
                all_links = container.select(link_selector)
            else:
                all_links = container.find_all("a", href=True)

            for link in all_links:
                # If using custom link selector, find <a> inside
                if link_selector != "a":
                    a_tag = link.find("a", href=True)
                    if a_tag:
                        href = a_tag.get("href", "")
                    else:
                        continue
                else:
                    a_tag = link
                    href = link.get("href", "")

                if not href:
                    continue

                full_url = urljoin(self.url, href)

                if not full_url.startswith("http"):
                    continue
                if full_url in seen_urls:
                    continue
                if "#" in full_url and full_url.split("#")[0] == self.url:
                    continue

                # Extract title: use custom selector or link text
                if title_selector:
                    title_el = link.select_one(title_selector)
                    title = title_el.get_text(strip=True) if title_el else ""
                else:
                    title = link.get_text(strip=True)

                if not title or len(title) < 4:
                    continue
                if title in ("首页", "关于", "联系", "更多", "下一页", "上一页", "登录", "注册"):
                    continue

                seen_urls.add(full_url)

                # Try to get summary from parent
                summary = ""
                parent = link.parent
                if parent:
                    for sibling in parent.find_all(["p", "span", "div"], recursive=False):
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 20 and text != title:
                            summary = text[:200]
                            break

                item = self._make_item(
                    title=title,
                    url=full_url,
                    summary=summary,
                    content_html=str(link),
                )
                items.append(item)

        return items[:50]
