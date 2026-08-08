"""AnySearch REST/JSON-RPC provider (discovery only)."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import requests

from discovery.models import SearchCandidate
from utils.helpers import now_iso

DEFAULT_BASE_URL = "https://api.anysearch.com/mcp"


class AnySearchProvider:
    """Calls AnySearch JSON-RPC ``tools/call`` / ``search``.

    ``snippet`` and ``provider_content`` are discovery-only and must never be
    written into ``SourceDocument`` / ``Evidence`` bodies.
    """

    name = "anysearch"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("ANYSEARCH_API_KEY", "")).strip()
        self.base_url = (
            base_url
            or os.getenv("ANYSEARCH_BASE_URL", "").strip()
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        language: str | None = None,
        region: str | None = None,
        domains: list[str] | None = None,
    ) -> list[SearchCandidate]:
        del language, region, domains  # reserved for future filters
        max_results = max(1, min(int(limit), 10))
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"query": query, "max_results": max_results},
            },
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = self._session.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if isinstance(body, dict) and body.get("error"):
            message = body["error"].get("message") if isinstance(body["error"], dict) else body["error"]
            raise RuntimeError(f"AnySearch error: {message}")

        rows = _extract_result_rows(body)
        discovered_at = now_iso()
        candidates: list[SearchCandidate] = []
        for idx, row in enumerate(rows[:max_results], start=1):
            url = str(row.get("url") or row.get("link") or "").strip()
            if not url or not urlparse(url).scheme.startswith("http"):
                continue
            title = str(row.get("title") or row.get("name") or url).strip()
            snippet = str(row.get("snippet") or row.get("description") or "").strip()
            provider_content = str(
                row.get("content") or row.get("provider_content") or row.get("text") or ""
            ).strip()
            candidates.append(
                SearchCandidate(
                    provider=self.name,
                    query=query,
                    title=title,
                    url=url,
                    snippet=snippet,
                    provider_content=provider_content,
                    rank=idx,
                    discovered_at=discovered_at,
                    language="zh-CN",
                    evidence_eligible=False,
                )
            )
        return candidates


def _extract_result_rows(body: Any) -> list[dict]:
    """Best-effort parse of MCP tools/call responses into dict rows."""
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    if not isinstance(body, dict):
        return []

    if isinstance(body.get("data"), list):
        return [row for row in body["data"] if isinstance(row, dict)]
    if isinstance(body.get("results"), list):
        return [row for row in body["results"] if isinstance(row, dict)]

    result = body.get("result")
    if isinstance(result, list):
        return [row for row in result if isinstance(row, dict)]
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                parsed = _parse_text_payload(text)
                if parsed:
                    return parsed
        for key in ("results", "data", "items"):
            if isinstance(result.get(key), list):
                return [row for row in result[key] if isinstance(row, dict)]
    return []


def _parse_text_payload(text: Any) -> list[dict]:
    if not isinstance(text, str) or not text.strip():
        return []
    raw = text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _parse_markdown_results(raw)
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    if isinstance(parsed, dict):
        for key in ("results", "data", "items"):
            if isinstance(parsed.get(key), list):
                return [row for row in parsed[key] if isinstance(row, dict)]
        if parsed.get("url"):
            return [parsed]
    return []


_MD_RESULT_RE = re.compile(
    r"###\s*\d+\.\s*(?P<title>.+?)\n"
    r"-\s*\*\*URL\*\*:\s*(?P<url>\S+)\s*\n"
    r"(?:-\s*(?P<snippet>.+?)(?=\n###\s*\d+\.|\Z))?",
    re.DOTALL,
)


def _parse_markdown_results(text: str) -> list[dict]:
    """Parse AnySearch MCP markdown search output into row dicts."""
    rows: list[dict] = []
    for match in _MD_RESULT_RE.finditer(text):
        title = match.group("title").strip()
        url = match.group("url").strip().rstrip(")")
        snippet = (match.group("snippet") or "").strip()
        # Truncate noisy markdown remnants
        if snippet.startswith("- "):
            snippet = snippet[2:].strip()
        rows.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet[:2000],
                "content": "",
            }
        )
    return rows
