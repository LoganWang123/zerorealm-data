"""Signal Repository — persist crawled signals to Supabase.

Aligned with Execution Architecture §2.3 (signals table).
Falls back to no-op when Supabase is not configured.

Usage::

    repo = SignalRepository()
    repo.save_batch(items)          # upsert RawItem list
    repo.exists(url, source_id)     # check duplicate
    repo.count_today()              # metrics
"""

from __future__ import annotations

from datetime import datetime

from crawlers.base import RawItem
from storage.db import get_client, is_db_available
from utils.helpers import CST
from utils.logger import get_logger


class SignalRepository:
    """Persist signals to Supabase ``signals`` table."""

    def __init__(self) -> None:
        self.logger = get_logger()
        self._available = is_db_available()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, item: RawItem) -> bool:
        """Insert a single signal. Returns True on success."""
        if not self._available:
            return False

        try:
            row = self._to_row(item)
            get_client().table("signals").upsert(
                row, on_conflict="id"
            ).execute()
            return True
        except Exception as e:
            self.logger.warning("[db] save signal failed: %s", e)
            return False

    def save_batch(self, items: list[RawItem]) -> int:
        """Batch upsert signals. Returns count of saved rows."""
        if not self._available or not items:
            return 0

        try:
            rows = [self._to_row(item) for item in items]
            # Supabase batch insert (chunked to avoid payload limit)
            chunk_size = 100
            saved = 0
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                get_client().table("signals").upsert(
                    chunk, on_conflict="id"
                ).execute()
                saved += len(chunk)

            self.logger.info("[db] Saved %d signals to Supabase", saved)
            return saved
        except Exception as e:
            self.logger.warning("[db] save_batch failed: %s", e)
            return 0

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def exists(self, url: str, source_id: str) -> bool:
        """Check if a signal with this URL already exists."""
        if not self._available:
            return False

        try:
            result = (
                get_client()
                .table("signals")
                .select("id")
                .eq("url", url)
                .eq("source_id", source_id)
                .limit(1)
                .execute()
            )
            return len(result.data) > 0
        except Exception:
            return False

    def count_today(self) -> int:
        """Count signals crawled today."""
        if not self._available:
            return 0

        try:
            today = datetime.now(CST).strftime("%Y-%m-%d")
            result = (
                get_client()
                .table("signals")
                .select("id", count="exact")
                .gte("crawled_at", f"{today}T00:00:00")
                .execute()
            )
            return result.count or 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _to_row(item: RawItem) -> dict:
        """Map RawItem → signals table row (aligned with §2.3 schema)."""
        return {
            "id": item.id,
            "tenant_id": "default",
            "source_id": item.source,
            "signal_type": item.metadata.get("category", "news"),
            "title": item.title,
            "url": item.url or None,
            "content_html": item.content_html or None,
            "content_text": item.content_text or None,
            "summary": item.summary or None,
            "author": item.author or None,
            "language": item.language,
            "published_at": item.published_at or None,
            "crawled_at": item.crawled_at,
            "run_id": item.run_id,
            "status": "raw",
            "http_status": item.http_status,
            "metadata": {
                "boost_score": item.metadata.get("boost_score"),
                "boost_level": item.metadata.get("boost_level"),
                "boost_matched": item.metadata.get("boost_matched"),
                "quality_score": item.metadata.get("quality_score"),
                "quality_dimensions": item.metadata.get("quality_dimensions"),
                "ner": item.metadata.get("ner"),
                "dedup_group_id": item.metadata.get("dedup_group_id"),
                "dedup_role": item.metadata.get("dedup_role"),
                "source_score": item.metadata.get("score"),
            },
        }
