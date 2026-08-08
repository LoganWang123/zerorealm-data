"""Tests for website Daily renderer / publisher / cross-channel checks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from publishing.asset_manager import AssetManager
from publishing.config import PublishConfig
from publishing.cross_channel import CROSS_CHANNEL_MISSING, find_cross_channel_issues
from publishing.factory import BuilderContext, PublisherFactory
from publishing.manifest_repository import ManifestRepository
from publishing.models import PublishStatus, RenderContext
from publishing.parser import ArticleParser
from publishing.website.mdx_adapter import build_website_daily_mdx
from publishing.workflow import PublishWorkflow

import publishing.website.builder  # noqa: F401


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _write_daily(path: Path, *, date: str, title: str, issue: int = 1) -> None:
    payload = {
        "title": title,
        "date": date,
        "issue": issue,
        "summary": [f"{title} summary"],
        "signal": f"signal for {date}",
        "sections": [
            {
                "level": "core",
                "title": f"{title} section",
                "excerpt": "excerpt",
                "source_url": "https://example.com",
                "source_name": "Example",
            }
        ],
        "cover": r"D:\local\cover.png",
    }
    path.write_text(
        "---\n"
        + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        + "---\n",
        encoding="utf-8",
    )


def test_build_website_daily_mdx_preserves_identity_and_strips_local_cover():
    source = """---
title: 同一篇日报
date: '2026-08-06'
issue: 11
summary:
  - 要点一
cover: D:/soft/AI/cover.png
sections:
  - level: core
    title: 核心
    excerpt: 摘要
    source_url: https://example.com
    source_name: Example
---
"""
    body = build_website_daily_mdx(source, date="2026-08-06", title="同一篇日报")
    data = yaml.safe_load(body.split("---", 2)[1])
    assert data["title"] == "同一篇日报"
    assert data["date"] == "2026-08-06"
    assert data["type"] == "daily"
    assert data["status"] == "published"
    assert data["slug"] == "daily-2026-08-06"
    assert "cover" not in data


def test_website_channel_roundtrip_matches_wechat_identity(tmp_path, monkeypatch):
    output_daily = tmp_path / "output_daily"
    output_daily.mkdir()
    website_daily = tmp_path / "website" / "content" / "daily"
    package_dir = tmp_path / "dist" / "content-package"
    date = "2026-08-06"
    title = "从「送得到」到「替你买」：这一周，智能柜运营商该盯住的三条线"
    _write_daily(output_daily / f"{date}.mdx", date=date, title=title, issue=11)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZEROREALM_WEBSITE_DAILY_DIR", str(website_daily))

    config = PublishConfig()
    config.website.content_dir = str(website_daily)
    config.website.package_dir = str(package_dir)
    manifest = ManifestRepository(tmp_path / "manifest.json")
    target = PublisherFactory.create(
        "website",
        BuilderContext(config=config, mode="draft", manifest=manifest),
    )
    workflow = PublishWorkflow(config=config, manifest=manifest)
    result = workflow.run(
        str(output_daily / f"{date}.mdx"),
        target,
        RenderContext(config=config, asset_manager=AssetManager()),
        mode="draft",
    )

    assert result.status == PublishStatus.SUCCESS
    assert result.url == f"/daily/{date}"
    website_path = website_daily / f"{date}.mdx"
    assert website_path.exists()
    article = ArticleParser().parse(str(output_daily / f"{date}.mdx"))
    site_data = yaml.safe_load(website_path.read_text(encoding="utf-8").split("---", 2)[1])
    assert site_data["title"] == article.title == title
    assert site_data["date"] == article.date == date
    assert site_data["slug"] == f"daily-{date}"
    entry = manifest.find(article.metadata.uuid, "website")
    assert entry is not None
    assert entry.generated is True
    assert entry.synced is True
    assert entry.deployed is False


def test_cross_channel_missing_when_wechat_ok_but_website_absent(tmp_path):
    output_daily = tmp_path / "output_daily"
    website_daily = tmp_path / "website_daily"
    output_daily.mkdir()
    website_daily.mkdir()
    date = "2026-08-06"
    title = "跨渠道缺失样例"
    _write_daily(output_daily / f"{date}.mdx", date=date, title=title, issue=11)
    article = ArticleParser().parse(str(output_daily / f"{date}.mdx"))

    manifest = ManifestRepository(tmp_path / "manifest.json")
    from publishing.models import PublishResult

    manifest.save(
        article.metadata.uuid,
        "wechat",
        PublishResult(status=PublishStatus.SUCCESS, channel="wechat", message="Draft created"),
    )

    issues = find_cross_channel_issues(
        output_daily_dir=output_daily,
        website_daily_dir=website_daily,
        manifest=manifest,
        now=datetime(2026, 8, 8, 12, 0, tzinfo=SHANGHAI),
    )
    assert len(issues) == 1
    assert issues[0].code == CROSS_CHANNEL_MISSING
    assert issues[0].date == date

    # After website artifact appears, check passes.
    (website_daily / f"{date}.mdx").write_text("---\ntitle: x\ndate: '2026-08-06'\n---\n", encoding="utf-8")
    assert (
        find_cross_channel_issues(
            output_daily_dir=output_daily,
            website_daily_dir=website_daily,
            manifest=manifest,
            now=datetime(2026, 8, 8, 12, 0, tzinfo=SHANGHAI),
        )
        == []
    )
