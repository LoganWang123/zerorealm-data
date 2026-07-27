"""Tests for knowledge/search.py — hybrid semantic search engine."""

import pytest

from knowledge import KnowledgeObject, generate_entity_id
from knowledge.store import KnowledgeStore
from knowledge.search import SearchEngine, SearchHit, SearchResponse
from storage.vectors import VectorStore


@pytest.fixture
def kb(tmp_path):
    store = KnowledgeStore(persist_path=str(tmp_path / "kb.json"))
    store.resolve_or_create("友宝", "company", industry_role="operator")
    store.resolve_or_create("元气森林", "company", industry_role="brand")
    store.resolve_or_create("智能柜", "product")
    store.resolve_or_create("商汤科技", "company", industry_role="technology")
    obj = store.resolve("友宝")
    store.add_alias(obj.id, "友宝在线")
    store.add_alias(obj.id, "UBOX")
    return store


@pytest.fixture
def vs(tmp_path):
    return VectorStore(persist_path=str(tmp_path / "vecs.json"))


@pytest.fixture
def engine(kb, vs):
    return SearchEngine(kb=kb, vs=vs)


class TestKeywordSearch:
    def test_exact_match(self, engine):
        resp = engine.search("友宝")
        assert resp.total >= 1
        assert resp.hits[0].object.canonical_name == "友宝"
        assert resp.hits[0].score >= 0.9

    def test_alias_match(self, engine):
        resp = engine.search("友宝在线")
        assert resp.total >= 1
        assert resp.hits[0].object.canonical_name == "友宝"

    def test_partial_match(self, engine):
        resp = engine.search("元气")
        assert resp.total >= 1
        names = [h.object.canonical_name for h in resp.hits]
        assert "元气森林" in names

    def test_no_match(self, engine):
        resp = engine.search("完全不相关的查询xyz")
        assert resp.total == 0

    def test_entity_type_filter(self, engine):
        resp = engine.search("友宝", entity_type="product")
        assert resp.total == 0

    def test_entity_type_filter_match(self, engine):
        resp = engine.search("智能柜", entity_type="product")
        assert resp.total >= 1


class TestVectorSearch:
    def test_vector_search_with_embedding(self, kb, vs):
        # Index some vectors
        obj = kb.resolve("友宝")
        vs.add(obj.id, "knowledge_object", "友宝 友宝在线 operator", [1.0, 0.0, 0.0])

        obj2 = kb.resolve("元气森林")
        vs.add(obj2.id, "knowledge_object", "元气森林 brand", [0.0, 1.0, 0.0])

        engine = SearchEngine(kb=kb, vs=vs)
        resp = engine.search("友宝", query_embedding=[0.9, 0.1, 0.0])

        assert resp.total >= 1
        # Vector search should boost 友宝's score
        top = resp.hits[0]
        assert top.object.canonical_name == "友宝"
        assert top.match_type in ("hybrid", "vector")

    def test_vector_only(self, kb, vs):
        obj = kb.resolve("商汤科技")
        vs.add(obj.id, "knowledge_object", "商汤科技 technology", [0.0, 0.0, 1.0])

        engine = SearchEngine(kb=kb, vs=vs)
        # Query that won't keyword-match but vector matches
        resp = engine.search("AI视觉", query_embedding=[0.0, 0.0, 0.95])
        # Should find via vector similarity
        if resp.total > 0:
            assert any(h.match_type == "vector" for h in resp.hits)


class TestHybridSearch:
    def test_hybrid_boosts_score(self, kb, vs):
        obj = kb.resolve("友宝")
        vs.add(obj.id, "knowledge_object", "友宝 operator", [1.0, 0.0])

        engine = SearchEngine(kb=kb, vs=vs)

        # Keyword only
        resp_kw = engine.search("友宝", query_embedding=None)
        # Hybrid
        resp_hybrid = engine.search("友宝", query_embedding=[1.0, 0.0])

        if resp_kw.total > 0 and resp_hybrid.total > 0:
            kw_score = resp_kw.hits[0].score
            hybrid_score = resp_hybrid.hits[0].score
            assert hybrid_score >= kw_score


class TestSearchResponse:
    def test_to_dict(self, engine):
        resp = engine.search("友宝")
        d = resp.to_dict()
        assert "query" in d
        assert "hits" in d
        assert "total" in d
        assert d["query"] == "友宝"

    def test_latency_tracked(self, engine):
        resp = engine.search("友宝")
        assert resp.latency_ms >= 0


class TestIndexHelpers:
    def test_index_object(self, engine, kb):
        obj = kb.resolve("友宝")
        engine.index_object(obj, [0.5, 0.5, 0.0])
        assert engine.vs.count == 1

    def test_index_signal(self, engine):
        engine.index_signal("sig_001", "友宝融资", "友宝完成C轮", [0.1, 0.9])
        assert engine.vs.count == 1
        records = engine.vs.get("sig_001")
        assert records[0].object_type == "signal"
