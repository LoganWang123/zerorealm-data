"""Adapt Daily source MDX into a website-safe artifact.

Keeps title/date/summary/sections/sources semantics identical to the WeChat
source article; only strips local-only media paths and ensures publication
metadata fields the website eligibility gate understands.
"""

from __future__ import annotations

from pathlib import Path

import yaml


LOCAL_PATH_MARKERS = (":\\", ":/", "/Users/", "/home/", "D:/", "d:/", "C:/", "c:/")


def _is_local_path(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith(("http://", "https://", "/media/", "media/")):
        return False
    return any(marker in text for marker in LOCAL_PATH_MARKERS) or (
        len(text) > 1 and text[1] == ":"
    )


def _strip_local_media(data: dict) -> dict:
    cleaned = dict(data)
    cover = cleaned.get("cover")
    if isinstance(cover, str) and _is_local_path(cover):
        cleaned.pop("cover", None)
    inline = cleaned.get("inline_images")
    if isinstance(inline, list):
        kept = [item for item in inline if isinstance(item, str) and not _is_local_path(item)]
        if kept:
            cleaned["inline_images"] = kept
        else:
            cleaned.pop("inline_images", None)
    return cleaned


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body after second ---)."""
    text = content.strip()
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        data = {}
    return data, parts[2].lstrip("\n")


def build_website_daily_mdx(
    source_text: str,
    *,
    date: str,
    title: str,
    status: str = "published",
    visibility: str = "public",
) -> str:
    """Build website Daily MDX from the canonical Daily source text."""
    data, body = extract_frontmatter(source_text)
    data = _strip_local_media(data)

    # Preserve identity; do not invent a new title/date.
    data["title"] = title or data.get("title") or ""
    data["date"] = date or str(data.get("date") or "")
    data["type"] = "daily"
    data["status"] = data.get("status") or status
    data["visibility"] = data.get("visibility") or visibility
    if "slug" not in data or not data.get("slug"):
        data["slug"] = f"daily-{data['date']}"

    dumped = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip() + "\n"
    if body.strip():
        return f"---\n{dumped}---\n{body}"
    return f"---\n{dumped}---\n"


def load_source_daily_mdx(date: str, root: Path | None = None) -> Path:
    """Resolve output_daily/<date>.mdx."""
    base = root or Path.cwd()
    path = base / "output_daily" / f"{date}.mdx"
    if not path.exists():
        raise FileNotFoundError(f"Daily source not found: {path}")
    return path
