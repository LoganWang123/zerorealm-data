"""Curated smart-cabinet foundation graph and research-operation artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from knowledge.industry_graph import (
    validate_graph_layer,
    validate_maintenance_status,
    validate_node_kind,
)
from knowledge.store import KnowledgeStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_GRAPH_PATH = REPOSITORY_ROOT / "data" / "knowledge" / "industry-graph-foundation.json"
RESEARCH_CYCLES_PATH = REPOSITORY_ROOT / "data" / "research" / "first-quarter-research.json"
FEEDBACK_LOG_PATH = REPOSITORY_ROOT / "data" / "research" / "feedback-log.json"


@dataclass(frozen=True)
class FoundationNode:
    name: str
    entity_type: str
    node_kind: str
    primary_layer: str
    secondary_layers: tuple[str, ...]
    industry_role: str
    secondary_roles: tuple[str, ...]
    maintenance_status: str


@dataclass(frozen=True)
class ResearchCycle:
    cycle: int
    weeks: str
    question: str
    backup_topic: str
    evidence_threshold: str
    status: str


def load_foundation_nodes(path: Path = FOUNDATION_GRAPH_PATH) -> list[FoundationNode]:
    """Load and validate the approved L0-L7 node universe."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes: list[FoundationNode] = []
    for raw in payload["nodes"]:
        validate_node_kind(raw["node_kind"])
        validate_graph_layer(raw["primary_layer"])
        for layer in raw.get("secondary_layers", []):
            validate_graph_layer(layer)
        validate_maintenance_status(raw["maintenance_status"])
        nodes.append(
            FoundationNode(
                name=raw["name"],
                entity_type=raw["entity_type"],
                node_kind=raw["node_kind"],
                primary_layer=raw["primary_layer"],
                secondary_layers=tuple(raw.get("secondary_layers", [])),
                industry_role=raw.get("industry_role", ""),
                secondary_roles=tuple(raw.get("secondary_roles", [])),
                maintenance_status=raw["maintenance_status"],
            )
        )
    return nodes


def seed_foundation_graph(
    store: KnowledgeStore, path: Path = FOUNDATION_GRAPH_PATH
) -> list:
    """Seed nodes only; relationships require independently reviewed evidence."""
    seeded = []
    for node in load_foundation_nodes(path):
        seeded.append(
            store.resolve_or_create(
                node.name,
                node.entity_type,
                industry_role=node.industry_role,
                graph_layer=node.primary_layer,
                graph_layers=list(node.secondary_layers),
                secondary_roles=list(node.secondary_roles),
                maintenance_status=node.maintenance_status,
                node_kind=node.node_kind,
            )
        )
    return seeded


def load_research_cycles(path: Path = RESEARCH_CYCLES_PATH) -> list[ResearchCycle]:
    """Load the approved six-cycle first-quarter research plan."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        ResearchCycle(
            cycle=raw["cycle"],
            weeks=raw["weeks"],
            question=raw["question"],
            backup_topic=raw["backup_topic"],
            evidence_threshold=raw["evidence_threshold"],
            status=raw["status"],
        )
        for raw in sorted(payload["cycles"], key=lambda item: item["cycle"])
    ]


def build_public_snapshot(
    store: KnowledgeStore, cycles: list[ResearchCycle] | None = None
) -> dict:
    """Build a portable, public-safe view of the graph.

    Only independently evidenced, confirmed relations are included. A node being
    present in the foundation graph never implies a commercial relationship.
    """
    nodes = []
    for obj in sorted(store.list_objects(), key=lambda item: item.canonical_name):
        metadata = obj.metadata
        layers = metadata.get("graph_layers", [metadata.get("graph_layer")])
        layers = [layer for layer in layers if layer]
        nodes.append(
            {
                "id": obj.id,
                "name": obj.canonical_name,
                "entity_type": obj.entity_type,
                "node_kind": metadata.get("node_kind", "entity"),
                "primary_layer": metadata.get("graph_layer", layers[0] if layers else ""),
                "layers": layers,
                "industry_role": obj.industry_role,
                "secondary_roles": metadata.get("secondary_roles", []),
                "maintenance_status": metadata.get("maintenance_status", "background"),
            }
        )

    relations = []
    for relation in store.list_relations(status="confirmed"):
        relations.append(
            {
                "id": relation.id,
                "from_id": relation.from_id,
                "to_id": relation.to_id,
                "relation_type": relation.relation_type,
                "status": "confirmed",
                "evidence": relation.metadata["evidence"],
            }
        )

    current_cycles = cycles if cycles is not None else load_research_cycles()
    return {
        "schema_version": 1,
        "scope": "smart-cabinet-industry-foundation-graph-v1",
        "statistics": {
            "total_nodes": len(nodes),
            "core_nodes": sum(node["maintenance_status"] == "core" for node in nodes),
            "confirmed_relations": len(relations),
        },
        "nodes": nodes,
        "relations": relations,
        "research_cycles": [
            {
                "cycle": cycle.cycle,
                "weeks": cycle.weeks,
                "question": cycle.question,
                "backup_topic": cycle.backup_topic,
                "evidence_threshold": cycle.evidence_threshold,
                "status": cycle.status,
            }
            for cycle in current_cycles
        ],
    }
