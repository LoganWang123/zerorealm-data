"""Daily Digest generator."""

import os
from datetime import datetime

from crawlers.base import RawItem
from utils.logger import get_logger
from utils.helpers import today_path, now_iso, CST


def generate_digest(
    items: list[RawItem],
    base_dir: str = "data",
    date_path: str | None = None,
    run_id: str = "",
    priority_sources: list[str] | None = None,
) -> str:
    """Generate daily digest markdown from items. Returns file path."""
    logger = get_logger()
    path = date_path or today_path()
    out_dir = os.path.join(base_dir, "digest", path)
    os.makedirs(out_dir, exist_ok=True)

    priority_sources = priority_sources or []
    today_str = datetime.now(CST).strftime("%Y-%m-%d")

    # Group by source
    by_source: dict[str, list[RawItem]] = {}
    priority_items: list[RawItem] = []

    for item in items:
        if item.source in priority_sources:
            priority_items.append(item)
        by_source.setdefault(item.source, []).append(item)

    # Build digest
    lines = [
        "---",
        f'date: "{today_str}"',
        f'sources: {list(by_source.keys())}',
        f"count: {len(items)}",
        f'generated_at: "{now_iso()}"',
        f'run_id: "{run_id}"',
        "---",
        "",
        f"# 日报素材 {today_str}",
        "",
    ]

    # Priority section
    if priority_items:
        lines.append("## ⭐ 重点新闻")
        for item in priority_items:
            lines.append(f"- [{item.title}]({item.url}) - {item.summary[:80]}（{item.source} / P0）")
        lines.append("")

    # By source
    for source, source_items in by_source.items():
        if source in priority_sources:
            continue  # already shown
        lines.append(f"## {source}（{len(source_items)} 条）")
        for item in source_items:
            summary_short = item.summary[:80] if item.summary else ""
            lines.append(f"- [{item.title}]({item.url}) - {summary_short}")
        lines.append("")

    filepath = os.path.join(out_dir, "digest.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[digest] Generated: {filepath} ({len(items)} items)")
    return filepath
