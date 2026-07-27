"""Tests for processors/knowledge.py — NER → Knowledge pipeline."""

import pytest

from crawlers.base import RawItem
from knowledge.store import KnowledgeStore
from processors.knowledge import (
    apply_knowledge,
    process_item_knowledge,
    _infer_industry_role,
    _infer_segment,
)


def _make_item(item_id: str, title: str, ner: dict | None = None) -> RawItem:
    return RawItem(
        id=item_id,
        source="36kr_rss",
        source_type="rss",
        language="zh-CN",
        title=title,
        url=f"https://example.com/{item_id}",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text="",
        summary="",
        author="",
        metadata={"ner": ner} if ner else {},
    )


class TestInferIndustryRole:
    def test_known_company(self):
        assert _infer_industry_role("友宝", "company") == "operator"
        assert _infer_industry_role("元气森林", "company") == "brand"
        assert _infer_industry_role("商汤科技", "company") == "technology"

    def test_partial_match(self):
        assert _infer_industry_role("友宝在线", "company") == "operator"

    def test_unknown_company(self):
        assert _infer_industry_role("某未知公司", "company") == ""

    def test_technology_type(self):
        assert _infer_industry_role("视觉识别", "technology") == "technology"


class TestInferSegment:
    def test_known(self):
        assert _infer_segment("友宝") == "vending"
        assert _infer_segment("元气森林") == "beverage"

    def test_unknown(self):
        assert _infer_segment("某公司") == ""


class TestProcessItemKnowledge:
    @pytest.fixture
    def store(self, tmp_path):
        return KnowledgeStore(persist_path=str(tmp_path / "kb.json"))

    def test_no_ner(self, store):
        item = _make_item("x", "无NER数据")
        result = process_item_knowledge(item, store)
        assert result["entities_resolved"] == 0
        assert store.object_count == 0

    def test_entities_resolved(self, store):
        ner = {
            "entities": [
                {"text": "友宝", "type": "company", "confidence": 95},
                {"text": "智能柜", "type": "product", "confidence": 90},
            ],
            "events": [],
            "topics": ["无人零售"],
        }
        item = _make_item("sig1", "友宝智能柜", ner=ner)
        result = process_item_knowledge(item, store)
        assert result["entities_resolved"] == 2
        assert store.object_count == 2

        obj = store.resolve("友宝")
        assert obj is not None
        assert obj.industry_role == "operator"

    def test_relations_from_events(self, store):
        ner = {
            "entities": [
                {"text": "丰e足食", "type": "company", "confidence": 95},
                {"text": "美团", "type": "company", "confidence": 90},
            ],
            "events": [
                {"type": "cooperation", "subject": "丰e足食", "action": "入驻", "object": "美团", "confidence": 88},
            ],
            "topics": [],
        }
        item = _make_item("sig2", "丰e足食入驻美团", ner=ner)
        result = process_item_knowledge(item, store)
        assert result["relations_created"] == 1
        assert store.relation_count == 1

    def test_dedup_across_items(self, store):
        ner1 = {
            "entities": [{"text": "友宝", "type": "company", "confidence": 95}],
            "events": [],
            "topics": [],
        }
        ner2 = {
            "entities": [{"text": "友宝", "type": "company", "confidence": 90}],
            "events": [],
            "topics": [],
        }
        item1 = _make_item("sig1", "友宝新闻1", ner=ner1)
        item2 = _make_item("sig2", "友宝新闻2", ner=ner2)

        process_item_knowledge(item1, store)
        process_item_knowledge(item2, store)

        assert store.object_count == 1
        obj = store.resolve("友宝")
        assert obj.mention_count == 2


class TestApplyKnowledge:
    def test_batch_processing(self, tmp_path):
        store = KnowledgeStore(persist_path=str(tmp_path / "kb.json"))
        items = [
            _make_item("s1", "友宝融资", ner={
                "entities": [{"text": "友宝", "type": "company", "confidence": 95}],
                "events": [],
                "topics": [],
            }),
            _make_item("s2", "元气森林新品", ner={
                "entities": [{"text": "元气森林", "type": "company", "confidence": 90}],
                "events": [],
                "topics": [],
            }),
            _make_item("s3", "无NER"),  # no NER data
        ]

        result = apply_knowledge(items, store, persist=False)
        assert len(result) == 3  # items unchanged
        assert store.object_count == 2

    def test_persist(self, tmp_path):
        path = str(tmp_path / "kb.json")
        store = KnowledgeStore(persist_path=path)
        items = [
            _make_item("s1", "友宝", ner={
                "entities": [{"text": "友宝", "type": "company", "confidence": 95}],
                "events": [],
                "topics": [],
            }),
        ]
        apply_knowledge(items, store, persist=True)
        assert os.path.exists(path)

    def test_empty_items(self, tmp_path):
        store = KnowledgeStore(persist_path=str(tmp_path / "kb.json"))
        result = apply_knowledge([], store, persist=False)
        assert result == []
        assert store.object_count == 0


import os  # noqa: E402 (used in test_persist)
