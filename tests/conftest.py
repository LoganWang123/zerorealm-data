"""Shared test fixtures."""

import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from crawlers.base import RawItem


@pytest.fixture
def sample_item() -> RawItem:
    """A typical crawled news item."""
    return RawItem(
        id="abc123",
        source="36kr_rss",
        source_type="rss",
        language="zh-CN",
        title="友宝完成新一轮融资，估值超50亿元",
        url="https://36kr.com/p/123456",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="20260726_090000",
        crawl_status="success",
        http_status=200,
        content_html="<p>友宝在线宣布完成C轮融资...</p>",
        content_text="友宝在线宣布完成C轮融资，由某知名投资机构领投，融资额超过5亿元人民币。",
        summary="友宝完成C轮融资，估值超50亿元。",
        author="36氪",
        tags=["融资", "无人零售"],
        metadata={"category": "news", "score": 80},
    )


@pytest.fixture
def low_quality_item() -> RawItem:
    """A low-quality item with minimal content."""
    return RawItem(
        id="def456",
        source="unknown_web",
        source_type="web",
        language="zh-CN",
        title="短标题",
        url="",
        published_at="",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="20260726_090000",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text="",
        summary="",
        author="",
        tags=[],
        metadata={"category": "news", "score": 30},
    )
