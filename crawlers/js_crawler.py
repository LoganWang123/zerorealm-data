"""JS-rendered web crawler using Playwright for SPA pages."""

import asyncio
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, RawItem
from utils.logger import get_logger


class JSCrawler(BaseCrawler):
    """Crawler for JavaScript-rendered pages (SPAs) using Playwright."""

    async def fetch(self) -> list[RawItem]:
        """Fetch page with JS rendering and parse links."""
        from playwright.async_api import async_playwright

        logger = get_logger()
        logger.debug(f"[{self.source_id}] Launching browser...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent=self.user_agent,
                locale="zh-CN",
            )

            try:
                await page.goto(self.url, timeout=self.timeout * 1000, wait_until="networkidle")
                # Wait a bit more for dynamic content
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

        all_links = soup.find_all("a", href=True)

        for link in all_links:
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
