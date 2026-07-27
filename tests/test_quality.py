"""Tests for processors/quality.py — quality scoring."""

import pytest

from crawlers.base import RawItem
from processors.quality import (
    score_item_rule,
    apply_quality,
    QualityResult,
    DimensionScore,
    _freshness_score,
    _parse_llm_score,
)


def _make_item(
    title: str = "友宝完成新一轮融资",
    url: str = "https://example.com/1",
    summary: str = "友宝在线宣布完成C轮融资，估值超50亿元。",
    content: str = "友宝在线宣布完成C轮融资，由某知名投资机构领投。" * 5,
    source_score: int = 80,
    boost_score: int = 15,
    published_at: str = "2026-07-26T08:00:00+08:00",
) -> RawItem:
    return RawItem(
        id="test",
        source="36kr_rss",
        source_type="rss",
        language="zh-CN",
        title=title,
        url=url,
        published_at=published_at,
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text=content,
        summary=summary,
        author="",
        metadata={"score": source_score, "boost_score": boost_score},
    )


class TestScoreItemRule:
    def test_high_quality_item(self):
        item = _make_item()
        result = score_item_rule(item)
        assert result.total >= 60
        assert result.method == "rule"
        assert len(result.dimensions) == 4

    def test_low_quality_item(self):
        item = _make_item(
            title="短",
            url="",
            summary="",
            content="",
            source_score=20,
            boost_score=0,
            published_at="",
        )
        result = score_item_rule(item)
        assert result.total < 40

    def test_dimensions_sum_to_total(self):
        item = _make_item()
        result = score_item_rule(item)
        weighted = sum(d.score * d.weight for d in result.dimensions)
        assert abs(result.total - round(weighted)) <= 1

    def test_source_dimension_uses_metadata_score(self):
        item = _make_item(source_score=95)
        result = score_item_rule(item)
        source_dim = next(d for d in result.dimensions if d.name == "source")
        assert source_dim.score == 95

    def test_relevance_scales_with_boost(self):
        low = _make_item(boost_score=0)
        high = _make_item(boost_score=20)
        r_low = score_item_rule(low)
        r_high = score_item_rule(high)
        rel_low = next(d for d in r_low.dimensions if d.name == "relevance")
        rel_high = next(d for d in r_high.dimensions if d.name == "relevance")
        assert rel_high.score > rel_low.score

    def test_passes_property(self):
        item = _make_item()
        result = score_item_rule(item)
        assert result.passes == (result.total >= 70)


class TestFreshnessScore:
    def test_recent_is_100(self):
        from datetime import datetime, timedelta
        from utils.helpers import CST

        recent = (datetime.now(CST) - timedelta(hours=1)).isoformat()
        assert _freshness_score(recent) == 100

    def test_old_is_low(self):
        assert _freshness_score("2020-01-01T00:00:00+08:00") == 0

    def test_empty_is_neutral(self):
        assert _freshness_score("") == 50

    def test_invalid_is_neutral(self):
        assert _freshness_score("not-a-date") == 50


class TestParseLlmScore:
    def test_yaml_block(self):
        content = '```yaml\nscore: 82\nreason: "good"\n```'
        assert _parse_llm_score(content) == 82

    def test_plain_yaml(self):
        assert _parse_llm_score("score: 75") == 75

    def test_invalid_returns_none(self):
        assert _parse_llm_score("no score here") is None

    def test_out_of_range_returns_none(self):
        assert _parse_llm_score("score: 150") is None


class TestApplyQuality:
    def test_attaches_metadata(self):
        items = [_make_item(), _make_item(title="另一条新闻")]
        result = apply_quality(items)
        for item in result:
            assert "quality_score" in item.metadata
            assert "quality_dimensions" in item.metadata

    def test_sorts_descending(self):
        high = _make_item(boost_score=20, source_score=90)
        low = _make_item(boost_score=0, source_score=20, summary="", content="")
        result = apply_quality([low, high])
        assert result[0].metadata["quality_score"] >= result[1].metadata["quality_score"]

    def test_threshold_filters(self):
        high = _make_item(boost_score=20, source_score=90)
        low = _make_item(
            title="x", url="", summary="", content="",
            source_score=10, boost_score=0, published_at="",
        )
        result = apply_quality([high, low], threshold=50)
        assert all(i.metadata["quality_score"] >= 50 for i in result)
