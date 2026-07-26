"""HTML web crawler using requests + BeautifulSoup."""

import asyncio
import urllib3
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from crawlers.base import BaseCrawler, RawItem
from utils.helpers import now_iso

# Suppress InsecureRequestWarning when ssl_verify=false
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Browser-level default headers for anti-crawl evasion
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class HTMLCrawler(BaseCrawler):
    """Crawler for HTML web pages (list pages with article links)."""

    def __init__(self, source_config: dict, run_id: str):
        super().__init__(source_config, run_id)
        self.parser_type = source_config.get("parser", "list")
        # Source-specific CSS selectors (can be overridden in sources.yaml)
        self.selectors = source_config.get("selectors", {})
        # SSL verification control (disable for self-signed / mismatched certs)
        self.ssl_verify = source_config.get("ssl_verify", True)
        # Whether to use browser-level headers (for anti-crawl sites)
        self.browser_headers = source_config.get("browser_headers", True)

    async def fetch(self) -> list[RawItem]:
        """Fetch and parse HTML page."""
        if self.browser_headers:
            headers = {**BROWSER_HEADERS}
            # Override UA if explicitly configured
            if self.user_agent != "zerorealm-bot/1.0":
                headers["User-Agent"] = self.user_agent
        else:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

        response = await asyncio.to_thread(
            requests.get,
            self.url,
            headers=headers,
            timeout=self.timeout,
            verify=self.ssl_verify,
        )

        if response.status_code != 200:
            raise ConnectionError(f"HTTP {response.status_code}")

        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "lxml")

        if self.parser_type == "article":
            return self._parse_article_page(soup)
        else:
            return self._parse_list_page(soup)

    def _parse_list_page(self, soup: BeautifulSoup) -> list[RawItem]:
        """Parse a list/index page containing article links."""
        items = []

        # Try configured selectors first, then fall back to common patterns
        link_selector = self.selectors.get("links", "a")
        title_selector = self.selectors.get("title")
        container_selector = self.selectors.get("container")

        if container_selector:
            containers = soup.select(container_selector)
        else:
            containers = [soup]

        seen_urls = set()

        for container in containers:
            links = container.select(link_selector) if link_selector != "a" else container.find_all("a", href=True)

            for link in links:
                href = link.get("href", "")
                if not href:
                    continue

                # Build absolute URL
                full_url = urljoin(self.url, href)

                # Filter: only http(s), skip duplicates, skip anchors
                if not full_url.startswith("http"):
                    continue
                if full_url in seen_urls:
                    continue
                if "#" in full_url and full_url.split("#")[0] == self.url:
                    continue

                # Extract title text
                title = link.get_text(strip=True)
                if not title or len(title) < 4:
                    continue
                # Skip navigation links
                if title in ("首页", "关于", "联系", "更多", "下一页", "上一页"):
                    continue

                seen_urls.add(full_url)

                # Try to get summary from sibling/parent text
                summary = self._extract_summary(link)

                item = self._make_item(
                    title=title,
                    url=full_url,
                    summary=summary,
                    content_html=str(link),
                )
                items.append(item)

        # Limit to reasonable count
        return items[:50]

    def _parse_article_page(self, soup: BeautifulSoup) -> list[RawItem]:
        """Parse a single article page (for company news detail pages)."""
        # Try to find article title
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        if not title:
            return []

        # Try to find article content
        content_selectors = ["article", ".article-content", ".content", ".news-content", "main"]
        content_html = ""
        content_text = ""

        for selector in content_selectors:
            el = soup.select_one(selector)
            if el:
                content_html = str(el)
                content_text = el.get_text(separator="\n", strip=True)
                break

        if not content_text:
            # Fallback: get all paragraph text
            paragraphs = soup.find_all("p")
            content_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Try to find publish date
        published_at = ""
        time_tag = soup.find("time") or soup.find(class_=lambda c: c and "time" in c.lower() if c else False)
        if time_tag:
            date_str = time_tag.get("datetime", "") or time_tag.get_text(strip=True)
            try:
                published_at = date_parser.parse(date_str).isoformat(timespec="seconds")
            except (ValueError, TypeError):
                pass

        item = self._make_item(
            title=title,
            url=self.url,
            content_html=content_html[:5000],
            content_text=content_text[:5000],
            summary=content_text[:200] if content_text else "",
            published_at=published_at,
        )

        return [item]

    def _extract_summary(self, link_tag) -> str:
        """Try to extract summary text near a link."""
        # Check parent element for additional text
        parent = link_tag.parent
        if parent:
            # Look for a summary/description sibling
            for sibling in parent.find_all(["p", "span", "div"], recursive=False):
                text = sibling.get_text(strip=True)
                if text and len(text) > 20 and text != link_tag.get_text(strip=True):
                    return text[:200]

        return ""
