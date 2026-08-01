"""Contracts for the curated smart-cabinet foundation graph."""

from __future__ import annotations

import json

from knowledge.foundation_graph import (
    FEEDBACK_LOG_PATH,
    FOUNDATION_GRAPH_PATH,
    RESEARCH_CYCLES_PATH,
    load_foundation_nodes,
    load_research_cycles,
    seed_foundation_graph,
)
from knowledge.store import KnowledgeStore


def test_foundation_graph_covers_all_layers_and_separates_archetypes():
    nodes = load_foundation_nodes()

    assert {node.primary_layer for node in nodes} == {
        "L0",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "L6",
        "L7",
    }
    assert next(node for node in nodes if node.name == "区域售货运营商").node_kind == "archetype"
    assert next(node for node in nodes if node.name == "丰e足食").node_kind == "entity"


def test_foundation_graph_has_twelve_core_nodes_and_deduplicates_cross_layer_entity():
    nodes = load_foundation_nodes()

    assert {node.name for node in nodes if node.maintenance_status == "core"} == {
        "元气森林",
        "农夫山泉",
        "伊利",
        "怡亚通",
        "易久批",
        "丰e足食",
        "友宝",
        "恒生活",
        "购吖",
        "中吉",
        "富宏智能",
        "海容冷链",
    }
    assert len([node for node in nodes if node.name == "海容冷链"]) == 1
    haierong = next(node for node in nodes if node.name == "海容冷链")
    assert haierong.primary_layer == "L4"
    assert haierong.secondary_layers == ("L7",)


def test_seed_creates_nodes_without_claiming_relations(tmp_path):
    store = KnowledgeStore(str(tmp_path / "foundation.json"))

    seeded = seed_foundation_graph(store)

    assert len(seeded) == len(load_foundation_nodes())
    assert store.relation_count == 0
    haierong = store.resolve("海容冷链")
    assert haierong is not None
    assert haierong.metadata["graph_layers"] == ["L4", "L7"]
    assert haierong.metadata["maintenance_status"] == "core"


def test_research_cycles_and_feedback_log_start_in_a_truthful_state():
    cycles = load_research_cycles()
    feedback = json.loads(FEEDBACK_LOG_PATH.read_text(encoding="utf-8"))

    assert FOUNDATION_GRAPH_PATH.exists()
    assert RESEARCH_CYCLES_PATH.exists()
    assert len(cycles) == 6
    assert [cycle.cycle for cycle in cycles] == [1, 2, 3, 4, 5, 6]
    assert all(cycle.status == "planned" for cycle in cycles)
    assert feedback == []
