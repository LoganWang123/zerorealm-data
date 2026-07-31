"""Shared taxonomy and evidence rules for ZeroRealm Industry Graph V2."""

from __future__ import annotations

from dataclasses import dataclass


INDUSTRY_LAYERS = {
    "L0": "regulator_association",
    "L1": "brand",
    "L2": "supply_chain",
    "L3": "operator",
    "L4": "hardware",
    "L5": "ai_saas_iot",
    "L6": "instant_retail",
    "L7": "infrastructure",
}

VALID_RELATION_TYPES = frozenset(
    {
        "supply",
        "purchase",
        "use",
        "integrate",
        "cooperate",
        "invest",
        "compete",
        "deliver",
        "pay",
        "subsidiary",
    }
)

EVIDENCE_LEVELS = ("A", "B", "C")
RELATION_STATUSES = frozenset({"confirmed", "observed", "revoked"})


@dataclass(frozen=True)
class EvidenceRef:
    """A public source that makes an Industry Graph fact traceable."""

    url: str
    published_at: str
    level: str
    source_name: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "published_at": self.published_at,
            "level": self.level,
            "source_name": self.source_name,
        }


def validate_graph_layer(graph_layer: str) -> None:
    """Reject layers outside the published L0-L7 taxonomy."""
    if graph_layer and graph_layer not in INDUSTRY_LAYERS:
        raise ValueError(f"unknown graph layer: {graph_layer}")


def validate_relation_evidence(relation_type: str, evidence: EvidenceRef | None) -> None:
    """Ensure a relationship presented as a fact has traceable public evidence."""
    if relation_type not in VALID_RELATION_TYPES:
        raise ValueError(f"unknown relation type: {relation_type}")
    if evidence is None:
        raise ValueError("evidence is required for a confirmed relationship")
    if not evidence.url.strip() or not evidence.published_at.strip():
        raise ValueError("evidence requires a source URL and publication date")
    if evidence.level not in EVIDENCE_LEVELS:
        raise ValueError("evidence level must be A, B, or C")


def evidence_meets_minimum(evidence: dict | None, minimum_level: str | None) -> bool:
    """Return whether evidence satisfies A > B > C ordering."""
    if minimum_level is None:
        return True
    if minimum_level not in EVIDENCE_LEVELS:
        raise ValueError("minimum evidence level must be A, B, or C")
    if not evidence:
        return False
    level = evidence.get("level")
    if level not in EVIDENCE_LEVELS:
        return False
    return EVIDENCE_LEVELS.index(level) <= EVIDENCE_LEVELS.index(minimum_level)
