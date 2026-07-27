"""Tests for storage/vectors.py — VectorStore and cosine similarity."""

import math

import pytest

from storage.vectors import (
    VectorStore,
    VectorRecord,
    SearchResult,
    cosine_similarity,
    generate_vector_id,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestGenerateVectorId:
    def test_deterministic(self):
        id1 = generate_vector_id("obj_001", 0)
        id2 = generate_vector_id("obj_001", 0)
        assert id1 == id2

    def test_different_chunks(self):
        id1 = generate_vector_id("obj_001", 0)
        id2 = generate_vector_id("obj_001", 1)
        assert id1 != id2


class TestVectorStore:
    @pytest.fixture
    def store(self, tmp_path):
        return VectorStore(persist_path=str(tmp_path / "vecs.json"))

    def test_add_and_count(self, store):
        store.add("obj1", "knowledge_object", "友宝融资", [1.0, 0.0, 0.0])
        assert store.count == 1

    def test_add_batch(self, store):
        items = [
            {"object_id": "o1", "object_type": "signal", "text": "text1", "embedding": [1.0, 0.0]},
            {"object_id": "o2", "object_type": "signal", "text": "text2", "embedding": [0.0, 1.0]},
        ]
        count = store.add_batch(items)
        assert count == 2
        assert store.count == 2

    def test_search_returns_ranked(self, store):
        store.add("o1", "signal", "友宝融资", [1.0, 0.0, 0.0])
        store.add("o2", "signal", "元气森林新品", [0.0, 1.0, 0.0])
        store.add("o3", "signal", "友宝合作", [0.9, 0.1, 0.0])

        results = store.search([1.0, 0.0, 0.0], top_k=3)
        assert len(results) == 3
        assert results[0].object_id == "o1"  # exact match
        assert results[0].score > results[1].score

    def test_search_top_k(self, store):
        for i in range(10):
            store.add(f"o{i}", "signal", f"text{i}", [float(i), 1.0])
        results = store.search([9.0, 1.0], top_k=3)
        assert len(results) == 3

    def test_search_threshold(self, store):
        store.add("o1", "signal", "match", [1.0, 0.0])
        store.add("o2", "signal", "no match", [0.0, 1.0])
        results = store.search([1.0, 0.0], threshold=0.5)
        assert len(results) == 1
        assert results[0].object_id == "o1"

    def test_search_filter_type(self, store):
        store.add("o1", "signal", "signal text", [1.0, 0.0])
        store.add("o2", "knowledge_object", "ko text", [1.0, 0.0])
        results = store.search([1.0, 0.0], object_type="signal")
        assert len(results) == 1
        assert results[0].record.object_type == "signal"

    def test_remove(self, store):
        store.add("o1", "signal", "text", [1.0, 0.0])
        store.add("o1", "signal", "text chunk2", [0.5, 0.5], chunk_index=1)
        assert store.count == 2
        removed = store.remove("o1")
        assert removed == 2
        assert store.count == 0

    def test_get_by_object(self, store):
        store.add("o1", "signal", "chunk0", [1.0, 0.0], chunk_index=0)
        store.add("o1", "signal", "chunk1", [0.0, 1.0], chunk_index=1)
        records = store.get("o1")
        assert len(records) == 2

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "vecs.json")
        store1 = VectorStore(persist_path=path)
        store1.add("o1", "signal", "友宝融资新闻", [0.1, 0.2, 0.3])
        store1.save()

        store2 = VectorStore(persist_path=path)
        assert store2.count == 1
        records = store2.get("o1")
        assert records[0].chunk_text == "友宝融资新闻"
        assert records[0].embedding == [0.1, 0.2, 0.3]

    def test_stats(self, store):
        store.add("o1", "signal", "t1", [1.0])
        store.add("o2", "knowledge_object", "t2", [1.0])
        stats = store.stats()
        assert stats["total_vectors"] == 2
        assert stats["by_type"]["signal"] == 1
        assert stats["by_type"]["knowledge_object"] == 1
