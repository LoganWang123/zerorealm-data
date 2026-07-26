"""Deduplication: check if item already exists."""

import glob
import os

from crawlers.base import RawItem
from utils.logger import get_logger


def is_duplicate(item: RawItem, base_dir: str = "data") -> bool:
    """Check if an item with the same ID already exists in data/raw/."""
    logger = get_logger()
    raw_dir = os.path.join(base_dir, "raw")
    if not os.path.exists(raw_dir):
        return False

    pattern = os.path.join(raw_dir, "**", f"{item.source}_{item.id}.json")
    matches = glob.glob(pattern, recursive=True)
    if matches:
        logger.debug(f"[dedup] Skip duplicate: {item.title[:30]}")
        return True
    return False


def filter_duplicates(items: list[RawItem], base_dir: str = "data") -> tuple[list[RawItem], int]:
    """Filter out duplicate items. Returns (new_items, dup_count)."""
    new_items = []
    dup_count = 0
    seen_ids = set()

    for item in items:
        # In-batch dedup
        if item.id in seen_ids:
            dup_count += 1
            continue
        # Historical dedup
        if is_duplicate(item, base_dir):
            dup_count += 1
            continue
        seen_ids.add(item.id)
        new_items.append(item)

    return new_items, dup_count
