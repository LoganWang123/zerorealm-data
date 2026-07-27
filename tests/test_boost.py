"""Tests for processors/boost.py — keyword boost scoring."""

import pytest

from crawlers.base import RawItem
from processors.boost import score_item, apply_boost, load_boost_config


@pytest.fixture
def config():
    """Minimal boost config for deterministic tests."""
    return {
        "core_keywords": {
            "weight": 10,
            "keywords": ["智能柜", "自动售货机", "无人零售"],
        },
        "role_keywords": {
            "operator": {
                "weight": 8,
                "keywords": ["点位", "铺设", "即时零售"],
            },
            "vendor": {
                "weight": 7,
                "keywords": ["柜型", "硬件", "制冷"],
            },
        },
        "event_keywords": {
            "expansion": {
                "weight": 8,
                "keywords": ["扩张", "新开", "布局"],
            },
        },
        "company_keywords": {
            "weight": 5,
            "keywords": ["友宝", "丰e足食"],
        },
        "rules": {
            "star_threshold": 10,
            "priority_threshold": 5,
        },
    }


def _make_item(title: str, summary: str = "", content: str = "") -> RawItem:
    return RawItem(
        id="test",
        source="test",
        source_type="rss",
        language="zh-CN",
        title=title,
        url="https://example.com",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text=content,
        summary=summary,
        author="",
        metadata={},
    )


class TestScoreItem:
    def test_core_keyword_hit(self, config):
        item = _make_item("智能柜行业迎来爆发期")
        score, matched = score_item(item, config)
        assert score >= 10
        assert any("core:智能柜" in m for m in matched)

    def test_multiple_keywords_accumulate(self, config):
        item = _make_item(
            "友宝扩张：新增万点位",
            summary="友宝加速布局即时零售",
        )
        score, matched = score_item(item, config)
        # company(5) + expansion(8) + operator(8) = 21
        assert score >= 21
        assert len(matched) >= 3

    def test_no_keyword_zero_score(self, config):
        item = _make_item("天气预报：明天有雨")
        score, matched = score_item(item, config)
        assert score == 0
        assert matched == []

    def test_case_insensitive(self, config):
        # "硬件" in config; test that matching works regardless of surrounding text
        item = _make_item("硬件设备采购")
        score, _ = score_item(item, config)
        assert score >= 7  # vendor:硬件


class TestApplyBoost:
    def test_sorts_by_score_descending(self, config):
        items = [
            _make_item("天气预报"),
            _make_item("智能柜行业报告"),
            _make_item("友宝布局新点位"),
        ]
        result = apply_boost(items, config)
        scores = [i.metadata["boost_score"] for i in result]
        assert scores == sorted(scores, reverse=True)

    def test_boost_level_star(self, config):
        items = [_make_item("智能柜自动售货机无人零售")]
        result = apply_boost(items, config)
        assert result[0].metadata["boost_level"] == "star"

    def test_boost_level_normal(self, config):
        items = [_make_item("天气预报")]
        result = apply_boost(items, config)
        assert result[0].metadata["boost_level"] == "normal"
