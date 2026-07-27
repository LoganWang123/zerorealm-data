"""Tests for processors/semantic_dedup.py — title similarity clustering."""

import pytest

from crawlers.base import RawItem
from processors.semantic_dedup import (
    TfidfVectorizer,
    cosine_similarity,
    UnionFind,
    cluster_duplicates,
    apply_semantic_dedup,
    filter_duplicates_semantic,
    _tokenize,
)


def _make_item(item_id: str, title: str) -> RawItem:
    return RawItem(
        id=item_id,
        source="test",
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
        metadata={},
    )


class TestTokenize:
    def test_chinese_bigrams(self):
        tokens = _tokenize("智能柜")
        assert "智能" in tokens
        assert "能柜" in tokens

    def test_empty(self):
        assert _tokenize("") == []

    def test_single_char(self):
        assert _tokenize("a") == ["a"]

    def test_strips_punctuation(self):
        tokens = _tokenize("友宝！完成融资。")
        assert all("！" not in t and "。" not in t for t in tokens)


class TestTfidfVectorizer:
    def test_fit_builds_vocab(self):
        v = TfidfVectorizer().fit(["智能柜行业", "自动售货机"])
        assert len(v.vocab) > 0
        assert len(v.idf) > 0

    def test_transform_returns_sparse(self):
        v = TfidfVectorizer().fit(["智能柜行业报告"])
        vec = v.transform("智能柜行业")
        assert isinstance(vec, dict)
        assert len(vec) > 0

    def test_unknown_text_empty_vec(self):
        v = TfidfVectorizer().fit(["aaaa"])
        vec = v.transform("zzzz")
        assert vec == {}


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = {0: 1.0, 1: 2.0}
        assert abs(cosine_similarity(a, a) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = {0: 1.0}
        b = {1: 1.0}
        assert cosine_similarity(a, b) == 0.0

    def test_empty_vector(self):
        assert cosine_similarity({}, {0: 1.0}) == 0.0


class TestUnionFind:
    def test_initial_separate(self):
        uf = UnionFind(3)
        assert uf.find(0) != uf.find(1)

    def test_union_merges(self):
        uf = UnionFind(3)
        uf.union(0, 1)
        assert uf.find(0) == uf.find(1)

    def test_transitive(self):
        uf = UnionFind(4)
        uf.union(0, 1)
        uf.union(1, 2)
        assert uf.find(0) == uf.find(2)


class TestClusterDuplicates:
    def test_similar_titles_clustered(self):
        items = [
            _make_item("a", "友宝在线完成C轮融资"),
            _make_item("b", "友宝在线宣布完成C轮融资"),
            _make_item("c", "天气预报明天有雨"),
        ]
        groups = cluster_duplicates(items, threshold=0.5)
        assert len(groups) >= 1
        # a and b should be in same group
        group_ids = {}
        for g in groups:
            for iid in g.item_ids:
                group_ids[iid] = g.group_id
        assert group_ids.get("a") == group_ids.get("b")

    def test_dissimilar_not_clustered(self):
        items = [
            _make_item("a", "智能柜行业年度报告发布"),
            _make_item("b", "可口可乐新品上市计划"),
        ]
        groups = cluster_duplicates(items, threshold=0.7)
        assert len(groups) == 0

    def test_single_item_no_groups(self):
        items = [_make_item("a", "唯一一条")]
        assert cluster_duplicates(items) == []

    def test_empty_input(self):
        assert cluster_duplicates([]) == []


class TestApplySemanticDedup:
    def test_annotates_metadata(self):
        items = [
            _make_item("a", "友宝在线完成C轮融资"),
            _make_item("b", "友宝在线宣布完成C轮融资"),
        ]
        items, groups = apply_semantic_dedup(items, threshold=0.5)
        # At least one should be flagged
        roles = [i.metadata.get("dedup_role") for i in items]
        assert "representative" in roles or "duplicate" in roles

    def test_no_duplicates_unchanged(self):
        items = [
            _make_item("a", "智能柜行业报告"),
            _make_item("b", "可口可乐新品发布"),
        ]
        items, groups = apply_semantic_dedup(items, threshold=0.8)
        assert all("dedup_group_id" not in i.metadata for i in items)


class TestFilterDuplicatesSemantic:
    def test_removes_duplicates(self):
        items = [
            _make_item("a", "友宝在线完成C轮融资"),
            _make_item("b", "友宝在线宣布完成C轮融资"),
            _make_item("c", "天气预报明天有雨"),
        ]
        kept, removed = filter_duplicates_semantic(items, threshold=0.5)
        assert removed >= 1
        assert len(kept) + removed == 3
        # c should always be kept
        assert any(i.id == "c" for i in kept)
