"""WebsitePublisher — write Daily MDX artifact + optional website sync."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from publishing.base import BasePublisher
from publishing.models import PublishResult, PublishStatus, WebsiteMetadata

if TYPE_CHECKING:
    from publishing.manifest_repository import ManifestRepository
    from publishing.models import RenderResult


def default_website_daily_dir() -> Path:
    """Sibling zerorealm-website/content/daily when repos are checked out together."""
    env = os.getenv("ZEROREALM_WEBSITE_DAILY_DIR", "").strip()
    if env:
        return Path(env)
    return (
        Path(__file__).resolve().parents[2].parent
        / "zerorealm-website"
        / "content"
        / "daily"
    )


class WebsitePublisher(BasePublisher):
    """Persist website Daily artifacts without touching WeChat."""

    def __init__(
        self,
        *,
        content_dir: Path | None = None,
        package_dir: Path | None = None,
        manifest: ManifestRepository | None = None,
    ):
        self._content_dir = content_dir or default_website_daily_dir()
        self._package_dir = package_dir or Path("dist/content-package")
        self._manifest = manifest

    def publish(
        self,
        result: RenderResult,
        dry_run: bool = False,
        publish_now: bool = False,
        notify_followers: bool = False,
    ) -> PublishResult:
        del publish_now, notify_followers
        start = time.time()
        meta = result.channel_metadata
        date = meta.slug if isinstance(meta, WebsiteMetadata) and meta.slug else ""
        if not date:
            return PublishResult(
                status=PublishStatus.FAILED,
                channel="website",
                message="Website render missing date slug",
                duration=time.time() - start,
            )

        package_path = (
            self._package_dir / f"daily-{date}" / "website" / f"{date}.mdx"
        )
        website_path = self._content_dir / f"{date}.mdx"

        if dry_run:
            return PublishResult(
                status=PublishStatus.DRY_RUN,
                channel="website",
                url=f"/daily/{date}",
                message="Dry run: website MDX prepared, no write",
                duration=time.time() - start,
                raw_response={
                    "generated": False,
                    "synced": False,
                    "deployed": False,
                    "artifact_path": str(package_path),
                    "website_path": str(website_path),
                    "date": date,
                    "title": result.title,
                },
            )

        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(result.body, encoding="utf-8")

        synced = False
        env_dir = os.getenv("ZEROREALM_WEBSITE_DAILY_DIR", "").strip()
        website_root = (
            self._content_dir.parents[1]
            if len(self._content_dir.parts) >= 2
            else self._content_dir
        )
        should_sync = bool(env_dir) or website_root.exists() or self._content_dir.exists()
        if should_sync:
            self._content_dir.mkdir(parents=True, exist_ok=True)
            website_path.write_text(result.body, encoding="utf-8")
            synced = True

        return PublishResult(
            status=PublishStatus.SUCCESS,
            channel="website",
            url=f"/daily/{date}",
            message=(
                f"Website Daily written"
                f"{' and synced' if synced else ' (package only)'}: {date}"
            ),
            duration=time.time() - start,
            raw_response={
                "generated": True,
                "synced": synced,
                "deployed": False,
                "artifact_path": str(package_path).replace("\\", "/"),
                "website_path": str(website_path).replace("\\", "/") if synced else None,
                "date": date,
                "title": result.title,
                "slug": f"daily-{date}",
            },
        )
