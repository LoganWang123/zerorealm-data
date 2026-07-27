"""MediaStorage — 媒体上传抽象 + 本地实现.

缓存策略：sha256 变化 → 重新上传；否则复用已缓存的 UploadResult。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from publishing.base import BaseMediaStorage
from publishing.models import MediaReference, UploadResult

CACHE_PATH = Path(".cache/media.json")


class LocalMediaStorage(BaseMediaStorage):
    """本地 MediaStorage（dry-run / preview 用，不实际上传）."""

    def upload(self, ref: MediaReference) -> UploadResult:
        """本地模式：返回本地路径作为 URL."""
        return UploadResult(
            media_id=f"local_{ref.sha256[:8]}",
            remote_url=f"file://{ref.local_path}",
            expires_at=None,
        )


class CachedMediaStorage(BaseMediaStorage):
    """带缓存的 MediaStorage 装饰器.

    包装任意 BaseMediaStorage，基于 sha256 缓存上传结果。
    """

    def __init__(self, inner: BaseMediaStorage, cache_path: Path = CACHE_PATH):
        self._inner = inner
        self._cache_path = cache_path
        self._cache: dict = self._load_cache()

    def upload(self, ref: MediaReference) -> UploadResult:
        """上传（带 sha256 缓存）."""
        cache_key = ref.sha256
        if cache_key and cache_key in self._cache:
            cached = self._cache[cache_key]
            # 检查是否过期
            expires = cached.get("expires_at")
            if expires is None or datetime.fromisoformat(expires) > datetime.now(timezone.utc):
                return UploadResult(
                    media_id=cached["media_id"],
                    remote_url=cached["remote_url"],
                    expires_at=datetime.fromisoformat(expires) if expires else None,
                )

        # 实际上传
        result = self._inner.upload(ref)

        # 缓存
        if cache_key:
            self._cache[cache_key] = {
                "media_id": result.media_id,
                "remote_url": result.remote_url,
                "expires_at": result.expires_at.isoformat() if result.expires_at else None,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_cache()

        return result

    def _load_cache(self) -> dict:
        if self._cache_path.exists():
            with open(self._cache_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)
