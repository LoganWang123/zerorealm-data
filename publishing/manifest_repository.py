"""ManifestRepository — 发布记录持久化.

存储于 storage/manifest/manifest.json，不可清除。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from publishing.models import PublishResult

MANIFEST_PATH = Path("storage/manifest/manifest.json")


@dataclass
class ManifestEntry:
    """单条发布记录."""

    article_uuid: str
    channel: str
    status: str
    draft_id: str | None = None
    publish_id: str | None = None
    url: str | None = None
    last_step: str = ""
    created_at: str = ""
    updated_at: str = ""
    # Cross-channel / website extensions (optional, backward compatible)
    generated: bool | None = None
    synced: bool | None = None
    deployed: bool | None = None
    artifact_path: str | None = None
    website_path: str | None = None
    date: str | None = None
    title: str | None = None
    slug: str | None = None


class ManifestRepository:
    """发布记录持久化（storage/manifest/manifest.json）."""

    def __init__(self, path: Path = MANIFEST_PATH):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _key(self, article_uuid: str, channel: str) -> str:
        return f"{article_uuid}:{channel}"

    def save(self, article_uuid: str, channel: str, result: PublishResult) -> None:
        """保存发布记录."""
        now = datetime.now(timezone.utc).isoformat()
        key = self._key(article_uuid, channel)
        existing = self._data.get(key, {})

        entry = {
            "article_uuid": article_uuid,
            "channel": channel,
            "status": result.status.value,
            "draft_id": result.draft_id,
            "publish_id": result.publish_id,
            "url": result.url,
            "last_step": "publish",
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        # Minimal cross-channel status extension from publisher raw_response.
        raw = dict(result.raw_response or {})
        for field_name in (
            "generated",
            "synced",
            "deployed",
            "artifact_path",
            "website_path",
            "date",
            "title",
            "slug",
        ):
            if field_name in raw:
                entry[field_name] = raw[field_name]
        self._data[key] = entry
        self._save()

    def find(self, article_uuid: str, channel: str) -> ManifestEntry | None:
        """查找记录（返回 None 表示不存在）."""
        key = self._key(article_uuid, channel)
        data = self._data.get(key)
        if data is None:
            return None
        known = {f.name for f in fields(ManifestEntry)}
        payload = {k: v for k, v in data.items() if k in known}
        return ManifestEntry(**payload)

    def delete(self, article_uuid: str, channel: str) -> bool:
        """删除记录（强制重新发布）."""
        key = self._key(article_uuid, channel)
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def update_step(self, article_uuid: str, channel: str, step: str) -> None:
        """更新当前步骤."""
        key = self._key(article_uuid, channel)
        if key in self._data:
            self._data[key]["last_step"] = step
            self._data[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def mark_published(self, article_uuid: str, channel: str) -> None:
        """标记为已发布."""
        key = self._key(article_uuid, channel)
        if key in self._data:
            self._data[key]["status"] = "published"
            self._data[key]["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def mark_failed(self, article_uuid: str, channel: str, step: str) -> None:
        """标记为失败."""
        key = self._key(article_uuid, channel)
        now = datetime.now(timezone.utc).isoformat()
        if key not in self._data:
            self._data[key] = {
                "article_uuid": article_uuid,
                "channel": channel,
                "created_at": now,
            }
        self._data[key]["status"] = "failed"
        self._data[key]["last_step"] = step
        self._data[key]["updated_at"] = now
        self._save()

    def load_all(self) -> dict:
        """加载全部记录."""
        return self._data.copy()
