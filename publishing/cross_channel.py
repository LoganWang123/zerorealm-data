"""Cross-channel Daily consistency checks.

Fail-fast when WeChat has a published/draft-success Daily but the website
production artifact is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from publishing.manifest_repository import ManifestRepository
from publishing.parser import ArticleParser

SHANGHAI = ZoneInfo("Asia/Shanghai")
WECHAT_OK = frozenset({"success", "updated", "published"})
CROSS_CHANNEL_MISSING = "CROSS_CHANNEL_MISSING"


@dataclass(frozen=True)
class CrossChannelIssue:
    code: str
    date: str
    article_uuid: str
    title: str
    detail: str


def shanghai_today(now: datetime | None = None) -> str:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        current = current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI).date().isoformat()


def find_cross_channel_issues(
    *,
    output_daily_dir: Path,
    website_daily_dir: Path,
    manifest: ManifestRepository | None = None,
    now: datetime | None = None,
) -> list[CrossChannelIssue]:
    """Return issues for Daily articles published on WeChat but missing on website."""
    repo = manifest or ManifestRepository()
    parser = ArticleParser()
    today = shanghai_today(now)
    issues: list[CrossChannelIssue] = []

    if not output_daily_dir.exists():
        return issues

    for path in sorted(output_daily_dir.glob("*.mdx")):
        article = parser.parse(str(path))
        if article.metadata.source != "daily":
            continue
        if not article.date or article.date > today:
            continue
        wechat = repo.find(article.metadata.uuid, "wechat")
        if wechat is None or wechat.status not in WECHAT_OK:
            continue
        website_path = website_daily_dir / f"{article.date}.mdx"
        website_entry = repo.find(article.metadata.uuid, "website")
        # Production artifact is website content/daily — package alone is not enough.
        has_website_artifact = website_path.exists()
        if website_entry is not None and website_entry.status in WECHAT_OK:
            pass
        if not has_website_artifact:
            issues.append(
                CrossChannelIssue(
                    code=CROSS_CHANNEL_MISSING,
                    date=article.date,
                    article_uuid=article.metadata.uuid,
                    title=article.title,
                    detail=(
                        f"wechat={wechat.status} but missing website Daily artifact "
                        f"({website_path.as_posix()})"
                    ),
                )
            )
    return issues


def format_issues(issues: list[CrossChannelIssue]) -> str:
    lines = [f"{item.code}: {item.date} {item.title} ({item.detail})" for item in issues]
    return "\n".join(lines)
