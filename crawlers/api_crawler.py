"""API-based crawler for JSON/XML API endpoints (arXiv, Zhihu, etc.)."""

import asyncio
import json
import xml.etree.ElementTree as ET

import requests

from crawlers.base import BaseCrawler, RawItem
from utils.helpers import now_iso
from utils.logger import get_logger


def _safe_parse_xml(text: str) -> ET.Element:
    """Parse XML safely (standard library parser is safe by default since Python 3.x)."""
    return ET.fromstring(text)


class ArxivCrawler(BaseCrawler):
    """Crawler for arXiv API (export.arxiv.org/api/query)."""

    async def fetch(self) -> list[RawItem]:
        """Fetch papers from arXiv API."""
        # Use arXiv API with search query for retail/vending related AI
        api_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": "cat:cs.AI OR cat:cs.CV",
            "start": 0,
            "max_results": 30,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        response = await asyncio.to_thread(
            requests.get, api_url, params=params, timeout=self.timeout
        )

        if response.status_code != 200:
            raise ConnectionError(f"arXiv API HTTP {response.status_code}")

        # Parse Atom XML (safe parser, no external entities)
        root = _safe_parse_xml(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        items = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            link = entry.find("atom:id", ns)
            published = entry.find("atom:published", ns)

            if title is None or link is None:
                continue

            item = self._make_item(
                title=title.text.strip().replace("\n", " "),
                url=link.text.strip(),
                summary=summary.text.strip()[:300] if summary is not None else "",
                published_at=published.text if published is not None else "",
                metadata={"source_type": "arxiv", "language": "en"},
            )
            item.language = "en"
            items.append(item)

        return items


class ZhihuHotCrawler(BaseCrawler):
    """Crawler for Zhihu hot list (public API)."""

    async def fetch(self) -> list[RawItem]:
        """Fetch Zhihu hot list."""
        api_url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
        params = {"limit": 50}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.zhihu.com/hot",
        }

        response = await asyncio.to_thread(
            requests.get, api_url, params=params, headers=headers, timeout=self.timeout
        )

        if response.status_code != 200:
            raise ConnectionError(f"Zhihu API HTTP {response.status_code}")

        data = response.json()
        items = []

        for entry in data.get("data", []):
            target = entry.get("target", {})
            title = target.get("title", "")
            url = target.get("url", "")
            excerpt = target.get("excerpt", "")

            if not title or not url:
                continue

            # Ensure full URL
            if not url.startswith("http"):
                url = f"https://www.zhihu.com/question/{target.get('id', '')}"

            item = self._make_item(
                title=title,
                url=url,
                summary=excerpt[:200],
            )
            items.append(item)

        return items
