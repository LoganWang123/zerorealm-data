"""Integration tests — end-to-end pipeline verification.

Tests the full flow: RawItem → Boost → Quality → Semantic Dedup → Output.
No network / LLM / DB calls; all rule-based processors.
"""

import json
import os

import pytest

from crawlers.base import RawItem
from processors.boost import apply_boost
from processors.quality import apply_quality
from processors.semantic_dedup import apply_semantic_dedup
from processors.dedup import filter_duplicates
from generators.daily_report import format_materials


def _make_item(
    item_id: str,
    title: str,
    source: str = "36kr_rss",
    summary: str = "",
    content: str = "",
    url: str = "",
    score: int = 80,
) -> RawItem:
    return RawItem(
        id=item_id,
        source=source,
        source_type="rss",
        language="zh-CN",
        title=title,
        url=url or f"https://example.com/{item_id}",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test_run",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text=content,
        summary=summary,
        author="",
        metadata={"category": "news", "score": score},
    )


class TestPipelineEndToEnd:
    """Full pipeline: dedup → boost → quality → semantic_dedup → format."""

    def test_full_pipeline(self, tmp_path):
        items = [
            _make_item("a1", "友宝完成C轮融资，估值超50亿元",
                       summary="友宝在线宣布完成C轮融资。",
                       content="友宝在线宣布完成C轮融资，由某知名投资机构领投。" * 3),
            _make_item("a2", "友宝在线宣布完成C轮融资",
                       summary="友宝完成融资。",
                       content="友宝在线宣布完成C轮融资。"),
            _make_item("b1", "智能柜行业迎来爆发期",
                       summary="智能柜市场快速增长。",
                       content="智能柜市场在2026年迎来爆发期。" * 3),
            _make_item("c1", "天气预报明天有雨"),
        ]

        # Step 1: ID dedup
        new_items, dup_count = filter_duplicates(items, str(tmp_path))
        assert len(new_items) == 4
        assert dup_count == 0

        # Step 2: Boost
        new_items = apply_boost(new_items)
        # 友宝 + 融资 should score high
        boosted = {i.id: i.metadata["boost_score"] for i in new_items}
        assert boosted["a1"] > boosted["c1"]

        # Step 3: Quality
        new_items = apply_quality(new_items)
        for item in new_items:
            assert "quality_score" in item.metadata
            assert 0 <= item.metadata["quality_score"] <= 100

        # Step 4: Semantic dedup (lower threshold for integration test)
        new_items, groups = apply_semantic_dedup(new_items, threshold=0.35)
        # a1 and a2 share "友宝"+"完成"+"融资" bigrams → should cluster
        dup_roles = {i.id: i.metadata.get("dedup_role") for i in new_items}
        # At least one of a1/a2 should be flagged
        has_cluster = (
            dup_roles.get("a1") is not None or dup_roles.get("a2") is not None
        )
        assert has_cluster

        # Step 5: Format materials (should skip duplicates)
        items_as_dicts = [i.to_dict() for i in new_items]
        materials = format_materials(items_as_dicts)
        assert "友宝" in materials
        assert "智能柜" in materials

    def test_empty_pipeline(self, tmp_path):
        new_items, dup_count = filter_duplicates([], str(tmp_path))
        assert new_items == []
        assert dup_count == 0

    def test_all_duplicates(self, tmp_path):
        items = [
            _make_item("same", "重复标题"),
            _make_item("same", "重复标题"),
        ]
        new_items, dup_count = filter_duplicates(items, str(tmp_path))
        assert len(new_items) == 1
        assert dup_count == 1


class TestFormatMaterialsEnriched:
    """Test that format_materials uses NER/quality/dedup metadata."""

    def test_includes_quality_score(self):
        item = _make_item("q1", "测试标题", summary="测试摘要")
        item.metadata["quality_score"] = 85
        materials = format_materials([item.to_dict()])
        assert "质量分: 85/100" in materials

    def test_includes_ner_entities(self):
        item = _make_item("n1", "友宝融资")
        item.metadata["ner"] = {
            "entities": [{"text": "友宝", "type": "company", "confidence": 95}],
            "events": [{"type": "financing", "subject": "友宝", "action": "完成融资", "object": "", "confidence": 90}],
            "topics": ["无人零售"],
        }
        materials = format_materials([item.to_dict()])
        assert "友宝(company)" in materials
        assert "友宝完成融资" in materials
        assert "无人零售" in materials

    def test_skips_duplicates(self):
        item1 = _make_item("r1", "代表性新闻")
        item2 = _make_item("r2", "重复新闻")
        item2.metadata["dedup_role"] = "duplicate"
        materials = format_materials([item1.to_dict(), item2.to_dict()])
        assert "代表性新闻" in materials
        assert "重复新闻" not in materials


class TestStorageGracefulDegradation:
    """Storage layer should no-op when Supabase is not configured."""

    def test_signal_repo_noop_without_env(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_KEY", raising=False)

        from storage.db import is_db_available
        from storage.signals import SignalRepository

        assert is_db_available() is False

        repo = SignalRepository()
        item = _make_item("x", "test")
        assert repo.save(item) is False
        assert repo.save_batch([item]) == 0
        assert repo.exists("url", "src") is False
        assert repo.count_today() == 0
