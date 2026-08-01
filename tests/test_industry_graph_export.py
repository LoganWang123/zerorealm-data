"""Public snapshot contracts for the research website."""

from __future__ import annotations

import json

from knowledge.foundation_graph import (
    build_public_snapshot,
    load_research_cycles,
    seed_foundation_graph,
)
from knowledge.industry_graph import EvidenceRef
from knowledge.store import KnowledgeStore


def test_public_snapshot_only_exposes_confirmed_relations(tmp_path):
    store = KnowledgeStore(str(tmp_path / "kb.json"))
    seed_foundation_graph(store)
    seller = store.resolve("丰e足食")
    brand = store.resolve("元气森林")
    assert seller and brand

    store.add_relation(
        seller.id,
        brand.id,
        "supply",
        evidence=EvidenceRef(
            url="https://example.com/evidence",
            published_at="2026-08-01",
            level="A",
            source_name="test",
        ),
    )
    store.add_relation(seller.id, brand.id, "cooperate", status="observed")

    snapshot = build_public_snapshot(store, load_research_cycles())

    assert snapshot["schema_version"] == 1
    assert snapshot["statistics"]["total_nodes"] >= 60
    assert snapshot["statistics"]["core_nodes"] == 12
    assert snapshot["statistics"]["confirmed_relations"] == 1
    assert len(snapshot["relations"]) == 1
    assert snapshot["relations"][0]["status"] == "confirmed"
    assert snapshot["research_cycles"][0]["status"] == "planned"
    assert any(node["name"] == "海容冷链" and node["layers"] == ["L4", "L7"] for node in snapshot["nodes"])


def test_exporter_writes_portable_json(tmp_path):
    from scripts.export_industry_graph import export_industry_graph_snapshot

    output = tmp_path / "industry-graph.json"
    payload = export_industry_graph_snapshot(output, knowledge_path=tmp_path / "missing.json")

    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == payload
