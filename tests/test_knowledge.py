"""Tests for knowledge/ — KnowledgeObject, Relation, KnowledgeStore."""

import json
import os

import pytest

from knowledge import (
    KnowledgeObject,
    Relation,
    generate_entity_id,
    generate_relation_id,
)
from knowledge.store import KnowledgeStore


# ---------------------------------------------------------------------------
# KnowledgeObject
# ---------------------------------------------------------------------------


class TestKnowledgeObject:
    def test_create_with_defaults(self):
        obj = KnowledgeObject(id="abc", entity_type="company", canonical_name="友宝")
        assert obj.lifecycle == "draft"
        assert obj.confidence == 50
        assert obj.mention_count == 0
        assert obj.created_at != ""

    def test_add_alias(self):
        obj = KnowledgeObject(id="abc", entity_type="company", canonical_name="友宝")
        assert obj.add_alias("友宝在线") is True
        assert obj.add_alias("UBOX") is True
        assert obj.add_alias("友宝在线") is False  # duplicate
        assert obj.add_alias("友宝") is False  # same as canonical
        assert len(obj.aliases) == 2

    def test_add_alias_empty(self):
        obj = KnowledgeObject(id="abc", entity_type="company", canonical_name="友宝")
        assert obj.add_alias("") is False
        assert obj.add_alias("  ") is False

    def test_increment_mentions(self):
        obj = KnowledgeObject(id="abc", entity_type="company", canonical_name="友宝")
        obj.increment_mentions("sig_001")
        obj.increment_mentions("sig_002")
        obj.increment_mentions("sig_001")  # duplicate signal
        assert obj.mention_count == 3
        assert obj.source_signals == ["sig_001", "sig_002"]

    def test_to_dict(self):
        obj = KnowledgeObject(
            id="abc", entity_type="company", canonical_name="友宝",
            aliases=["友宝在线"], industry_role="operator",
        )
        d = obj.to_dict()
        assert d["id"] == "abc"
        assert d["entity_type"] == "company"
        assert d["canonical_name"] == "友宝"
        assert "友宝在线" in d["aliases"]


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


class TestIdGeneration:
    def test_deterministic(self):
        id1 = generate_entity_id("company", "友宝")
        id2 = generate_entity_id("company", "友宝")
        assert id1 == id2

    def test_case_insensitive(self):
        id1 = generate_entity_id("company", "友宝")
        id2 = generate_entity_id("company", "友宝 ")
        assert id1 == id2

    def test_different_types_different_ids(self):
        id1 = generate_entity_id("company", "友宝")
        id2 = generate_entity_id("product", "友宝")
        assert id1 != id2

    def test_relation_id_deterministic(self):
        id1 = generate_relation_id("a", "b", "cooperate")
        id2 = generate_relation_id("a", "b", "cooperate")
        assert id1 == id2

    def test_relation_id_directional(self):
        id1 = generate_relation_id("a", "b", "invest")
        id2 = generate_relation_id("b", "a", "invest")
        assert id1 != id2


# ---------------------------------------------------------------------------
# KnowledgeStore
# ---------------------------------------------------------------------------


class TestKnowledgeStore:
    @pytest.fixture
    def store(self, tmp_path):
        return KnowledgeStore(persist_path=str(tmp_path / "kb.json"))

    def test_resolve_or_create_new(self, store):
        obj = store.resolve_or_create("友宝", "company", signal_id="sig_001")
        assert obj.canonical_name == "友宝"
        assert obj.entity_type == "company"
        assert obj.mention_count == 1
        assert store.object_count == 1

    def test_resolve_existing(self, store):
        obj1 = store.resolve_or_create("友宝", "company", signal_id="sig_001")
        obj2 = store.resolve_or_create("友宝", "company", signal_id="sig_002")
        assert obj1.id == obj2.id
        assert obj2.mention_count == 2
        assert store.object_count == 1

    def test_resolve_by_alias(self, store):
        obj = store.resolve_or_create("友宝", "company")
        store.add_alias(obj.id, "友宝在线")
        resolved = store.resolve("友宝在线")
        assert resolved is not None
        assert resolved.id == obj.id

    def test_resolve_case_insensitive(self, store):
        store.resolve_or_create("SHEIN", "company")
        resolved = store.resolve("shein")
        assert resolved is not None

    def test_add_relation(self, store):
        obj1 = store.resolve_or_create("友宝", "company")
        obj2 = store.resolve_or_create("美团", "company")
        rel = store.add_relation(obj1.id, obj2.id, "cooperate", signal_id="sig_001")
        assert rel is not None
        assert rel.relation_type == "cooperate"
        assert store.relation_count == 1

    def test_add_relation_dedup(self, store):
        obj1 = store.resolve_or_create("友宝", "company")
        obj2 = store.resolve_or_create("美团", "company")
        store.add_relation(obj1.id, obj2.id, "cooperate")
        store.add_relation(obj1.id, obj2.id, "cooperate")  # duplicate
        assert store.relation_count == 1

    def test_add_relation_invalid_entity(self, store):
        rel = store.add_relation("nonexist1", "nonexist2", "cooperate")
        assert rel is None

    def test_get_relations(self, store):
        obj1 = store.resolve_or_create("友宝", "company")
        obj2 = store.resolve_or_create("美团", "company")
        obj3 = store.resolve_or_create("元气森林", "company")
        store.add_relation(obj1.id, obj2.id, "cooperate")
        store.add_relation(obj3.id, obj1.id, "supply")

        rels = store.get_relations(obj1.id)
        assert len(rels) == 2

    def test_list_objects_filter(self, store):
        store.resolve_or_create("友宝", "company")
        store.resolve_or_create("智能柜", "product")
        store.resolve_or_create("美团", "company")

        companies = store.list_objects(entity_type="company")
        assert len(companies) == 2

        products = store.list_objects(entity_type="product")
        assert len(products) == 1

    def test_stats(self, store):
        store.resolve_or_create("友宝", "company", industry_role="operator")
        store.resolve_or_create("智能柜", "product")
        stats = store.stats()
        assert stats["total_objects"] == 2
        assert stats["by_type"]["company"] == 1
        assert stats["by_type"]["product"] == 1

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "kb.json")

        # Create and save
        store1 = KnowledgeStore(persist_path=path)
        obj = store1.resolve_or_create("友宝", "company", signal_id="sig_001")
        store1.add_alias(obj.id, "友宝在线")
        obj2 = store1.resolve_or_create("美团", "company")
        store1.add_relation(obj.id, obj2.id, "cooperate")
        store1.save()

        # Load in new instance
        store2 = KnowledgeStore(persist_path=path)
        assert store2.object_count == 2
        assert store2.relation_count == 1
        resolved = store2.resolve("友宝在线")
        assert resolved is not None
        assert resolved.canonical_name == "友宝"

    def test_load_nonexistent_file(self, tmp_path):
        store = KnowledgeStore(persist_path=str(tmp_path / "nope.json"))
        assert store.object_count == 0
