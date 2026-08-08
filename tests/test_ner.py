"""Tests for processors/ner.py — entity extraction parsing."""

import pytest

from crawlers.base import RawItem
from processors.ner import (
    EntityMention,
    EventMention,
    NERResult,
    parse_ner_response,
)


def _make_item(title: str = "友宝完成C轮融资") -> RawItem:
    return RawItem(
        id="test",
        source="36kr_rss",
        source_type="rss",
        language="zh-CN",
        title=title,
        url="https://example.com/1",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text="友宝在线宣布完成C轮融资。",
        summary="友宝完成融资。",
        author="",
        metadata={},
    )


class TestParseNerResponse:
    def test_valid_yaml_block(self):
        content = """```yaml
entities:
  - text: "友宝"
    type: "company"
    confidence: 95
  - text: "智能柜"
    type: "product"
    confidence: 90
events:
  - type: "financing"
    subject: "友宝"
    action: "完成C轮融资"
    object: ""
    confidence: 90
topics:
  - "无人零售"
  - "融资"
```"""
        result = parse_ner_response(content)
        assert result is not None
        assert len(result.entities) == 2
        assert result.entities[0].text == "友宝"
        assert result.entities[0].entity_type == "company"
        assert result.entities[0].confidence == 95
        assert len(result.events) == 1
        assert result.events[0].event_type == "financing"
        assert result.events[0].subject == "友宝"
        assert result.topics == ["无人零售", "融资"]

    def test_empty_entities(self):
        content = """```yaml
entities: []
events: []
topics: []
```"""
        result = parse_ner_response(content)
        assert result is not None
        assert result.entity_count == 0
        assert result.event_count == 0

    def test_invalid_yaml_returns_none(self):
        assert parse_ner_response("not yaml at all {{{") is None

    def test_partial_output(self):
        content = """```yaml
entities:
  - text: "元气森林"
    type: "company"
    confidence: 88
```"""
        result = parse_ner_response(content)
        assert result is not None
        assert len(result.entities) == 1
        assert result.events == []
        assert result.topics == []

    def test_missing_fields_default(self):
        content = """```yaml
entities:
  - text: "北京"
events: []
topics: []
```"""
        result = parse_ner_response(content)
        assert result is not None
        assert result.entities[0].entity_type == "unknown"
        assert result.entities[0].confidence == 80


class TestNERResult:
    def test_companies_filter(self):
        result = NERResult(
            entities=[
                EntityMention("友宝", "company", 95),
                EntityMention("智能柜", "product", 90),
                EntityMention("元气森林", "company", 88),
            ],
        )
        assert result.companies() == ["友宝", "元气森林"]

    def test_to_dict(self):
        result = NERResult(
            entities=[EntityMention("友宝", "company", 95)],
            events=[EventMention("financing", "友宝", "融资")],
            topics=["融资"],
            model="deepseek-v4-flash",
            prompt_version=1,
        )
        d = result.to_dict()
        assert d["entities"][0]["text"] == "友宝"
        assert d["events"][0]["type"] == "financing"
        assert d["ner_model"] == "deepseek-v4-flash"
