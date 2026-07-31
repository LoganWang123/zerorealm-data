"""Behavior tests for the evidence-backed Industry Graph V2 contract."""

from __future__ import annotations

import pytest

from knowledge.industry_graph import EvidenceRef, validate_relation_evidence
from knowledge.store import KnowledgeStore


def test_confirmed_relationship_requires_traceable_evidence():
    """Removing a source URL, date, or accepted evidence level must block a fact claim."""
    with pytest.raises(ValueError, match="evidence"):
        validate_relation_evidence(
            "supply",
            EvidenceRef(url="", published_at="2026-07-31", level="A"),
        )


def test_store_persists_graph_layer_and_confirmed_evidence(tmp_path):
    """A confirmed graph fact remains queryable with its evidence after JSON reload."""
    path = str(tmp_path / "industry-graph.json")
    store = KnowledgeStore(path)
    brand = store.resolve_or_create("品牌 A", "company", graph_layer="L1")
    operator = store.resolve_or_create("运营商 B", "company", graph_layer="L3")
    relation = store.add_relation(
        brand.id,
        operator.id,
        "supply",
        evidence=EvidenceRef(
            url="https://example.com/announcement",
            published_at="2026-07-31",
            level="A",
            source_name="官方公告",
        ),
    )
    assert relation is not None
    store.save()

    restored = KnowledgeStore(path)
    assert restored.get(brand.id).metadata["graph_layer"] == "L1"
    confirmed = restored.list_relations(min_evidence_level="B")
    assert len(confirmed) == 1
    assert confirmed[0].metadata["evidence"]["url"] == "https://example.com/announcement"


def test_store_excludes_observed_relation_from_confirmed_query(tmp_path):
    """A weak observation must not appear among confirmed graph facts."""
    store = KnowledgeStore(str(tmp_path / "industry-graph.json"))
    first = store.resolve_or_create("设备商 A", "company", graph_layer="L4")
    second = store.resolve_or_create("运营商 B", "company", graph_layer="L3")
    store.add_relation(first.id, second.id, "use", status="observed")

    assert store.list_relations() == []
