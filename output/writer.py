"""Output writer: JSON + Markdown."""

import json
import os

from crawlers.base import RawItem
from utils.logger import get_logger
from utils.helpers import today_path


def write_raw_json(item: RawItem, base_dir: str = "data", date_path: str | None = None) -> str:
    """Write raw item as JSON file. Returns file path."""
    logger = get_logger()
    path = date_path or today_path()
    out_dir = os.path.join(base_dir, "raw", path)
    os.makedirs(out_dir, exist_ok=True)

    filename = f"{item.source}_{item.id}.json"
    filepath = os.path.join(out_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(item.to_dict(), f, ensure_ascii=False, indent=2)

    logger.debug(f"[writer] JSON: {filepath}")
    return filepath


def write_clean_markdown(item: RawItem, base_dir: str = "data", date_path: str | None = None) -> str:
    """Write cleaned item as Markdown file. Returns file path."""
    logger = get_logger()
    path = date_path or today_path()
    out_dir = os.path.join(base_dir, "clean", path)
    os.makedirs(out_dir, exist_ok=True)

    filename = f"{item.source}_{item.id}.md"
    filepath = os.path.join(out_dir, filename)

    # Build frontmatter + content
    content = item.content_text or item.summary or "(no content)"
    md = f"""---
title: "{item.title}"
source: "{item.source}"
url: "{item.url}"
date: "{item.published_at[:10] if item.published_at else ''}"
type: "{item.metadata.get('category', 'news')}"
---

{content}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    logger.debug(f"[writer] MD: {filepath}")
    return filepath
