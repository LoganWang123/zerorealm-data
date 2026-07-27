"""Knowledge Context — domain models.

Aligned with Execution Architecture §1.2 (Knowledge Context):
- KnowledgeObject: canonical entity (company / person / product / technology / location)
- Relation: typed edge between two KnowledgeObjects
- Entity resolution: mention → canonical ID
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from utils.helpers import CST


# ---------------------------------------------------------------------------
# KnowledgeObject
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeObject:
    """A canonical entity in the knowledge base.

    Aligned with Execution Architecture §2.5 (knowledge_objects table).
    """

    id: str                               # Canonical ID (deterministic)
    entity_type: str                      # company / person / product / technology / location
    canonical_name: str                   # Primary display name
    aliases: list[str] = field(default_factory=list)
    industry_role: str = ""               # operator / vendor / brand / technology / channel / capital
    industry_segment: str = ""            # beverage / dairy / ai / ...
    lifecycle: str = "draft"              # draft / verified / published / deprecated / archived
    confidence: int = 50                  # 0-100
    provenance: str = "derived"           # primary / secondary / derived / llm_generated / human_verified
    source_signals: list[str] = field(default_factory=list)  # signal IDs that contributed
    mention_count: int = 0                # how many times this entity was mentioned
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(CST).isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def add_alias(self, alias: str) -> bool:
        """Add an alias if not already present. Returns True if added."""
        alias_lower = alias.strip()
        if not alias_lower:
            return False
        existing = {a.lower() for a in self.aliases}
        if alias_lower.lower() in existing or alias_lower.lower() == self.canonical_name.lower():
            return False
        self.aliases.append(alias_lower)
        return True

    def increment_mentions(self, signal_id: str = "") -> None:
        """Track a new mention of this entity."""
        self.mention_count += 1
        if signal_id and signal_id not in self.source_signals:
            self.source_signals.append(signal_id)
        self.updated_at = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "industry_role": self.industry_role,
            "industry_segment": self.industry_segment,
            "lifecycle": self.lifecycle,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "source_signals": self.source_signals[-20:],  # keep last 20
            "mention_count": self.mention_count,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Relation
# ---------------------------------------------------------------------------


@dataclass
class Relation:
    """A typed relationship between two KnowledgeObjects.

    Aligned with Execution Architecture §2.5 (relations table).
    """

    id: str
    from_id: str                          # source KnowledgeObject ID
    to_id: str                            # target KnowledgeObject ID
    relation_type: str                    # invest / cooperate / compete / supply / subsidiary
    confidence: int = 50                  # 0-100
    provenance: str = "derived"           # derived / llm_generated / human_verified
    source_signal: str = ""               # signal that produced this relation
    metadata: dict = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "source_signal": self.source_signal,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def generate_entity_id(entity_type: str, canonical_name: str) -> str:
    """Deterministic entity ID from type + name (SHA256 first 16 chars)."""
    key = f"{entity_type}:{canonical_name.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def generate_relation_id(from_id: str, to_id: str, relation_type: str) -> str:
    """Deterministic relation ID."""
    key = f"{from_id}:{relation_type}:{to_id}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
