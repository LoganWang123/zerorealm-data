"""Deduplication: check if item already exists."""

import glob
import json
import os
from pathlib import Path

from crawlers.base import RawItem
from utils.logger import get_logger


def _item_key(item: RawItem) -> str:
    """Return a source-scoped key so IDs from different sources do not collide."""
    return f"{item.source}:{item.id}"


def _state_path(base_dir: str) -> Path:
    return Path(base_dir) / "state" / "seen_ids.json"


def load_seen_ids(base_dir: str = "data") -> set[str]:
    """Load the lightweight cross-run deduplication ledger."""
    path = _state_path(base_dir)
    if not path.exists():
        return set()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        get_logger().warning("[dedup] Ignoring unreadable state file: %s", path)
        return set()

    return {value for value in data if isinstance(value, str)}


def record_seen_items(items: list[RawItem], base_dir: str = "data") -> None:
    """Persist item IDs atomically for deduplication on the next CI run."""
    if not items:
        return

    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen_ids = load_seen_ids(base_dir)
    seen_ids.update(_item_key(item) for item in items)

    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(sorted(seen_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def is_duplicate(item: RawItem, base_dir: str = "data") -> bool:
    """Check the cross-run ledger and existing raw files for an item."""
    logger = get_logger()
    if _item_key(item) in load_seen_ids(base_dir):
        logger.debug(f"[dedup] Skip state duplicate: {item.title[:30]}")
        return True

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
    batch_ids = set()
    historical_ids = load_seen_ids(base_dir)

    for item in items:
        item_key = _item_key(item)
        # In-batch dedup
        if item_key in batch_ids:
            dup_count += 1
            continue
        batch_ids.add(item_key)

        if item_key in historical_ids:
            dup_count += 1
            continue

        # Historical dedup
        if is_duplicate(item, base_dir):
            dup_count += 1
            continue
        new_items.append(item)

    return new_items, dup_count
