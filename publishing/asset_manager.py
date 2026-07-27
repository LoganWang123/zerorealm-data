"""AssetManager — 素材管理.

封面、字体、Logo 等静态素材管理（hash 追踪）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from publishing.models import MediaReference


@dataclass
class AssetInfo:
    """素材信息."""

    path: str
    sha256: str
    mtime: float


class AssetManager:
    """素材管理器."""

    def __init__(self, base_dir: str = "assets"):
        self._base = Path(base_dir)
        self._cache: dict[str, AssetInfo] = {}

    def get_cover(self, article) -> MediaReference:
        """获取封面（优先 article.cover，否则 default）."""
        cover_path = article.cover if article.cover else str(self._base / "covers" / "default.png")
        path = Path(cover_path)

        if not path.exists():
            # 使用默认封面
            path = self._base / "covers" / "default.png"

        sha = self._file_hash(path) if path.exists() else ""

        return MediaReference(
            local_path=str(path),
            sha256=sha,
            mime="image/png",
            width=900,
            height=383,
        )

    def get_font(self, name: str) -> str:
        """获取字体路径."""
        return str(self._base / "fonts" / name)

    def get_logo(self) -> MediaReference:
        """获取 Logo."""
        path = self._base / "logo.png"
        sha = self._file_hash(path) if path.exists() else ""
        return MediaReference(
            local_path=str(path),
            sha256=sha,
            mime="image/png",
        )

    def invalidate(self, path: str) -> None:
        """清除缓存."""
        self._cache.pop(path, None)

    def _file_hash(self, path: Path) -> str:
        """计算文件 SHA256."""
        key = str(path)
        if key in self._cache:
            info = self._cache[key]
            mtime = path.stat().st_mtime
            if info.mtime == mtime:
                return info.sha256

        if not path.exists():
            return ""

        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)

        sha = h.hexdigest()
        self._cache[key] = AssetInfo(
            path=key,
            sha256=sha,
            mtime=path.stat().st_mtime,
        )
        return sha
