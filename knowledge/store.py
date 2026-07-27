"""Knowledge Store — in-memory entity registry with resolution.

M3: file-based (JSON), single-process.
M5+: migrate to Supabase knowledge_objects table.

Responsibilities:
- Maintain canonical entity registry
- Resolve mentions → canonical KnowledgeObject (alias matching)
- Track relations between entities
- Persist / load from JSON file
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from knowledge import (
    KnowledgeObject,
    Relation,
    generate_entity_id,
    generate_relation_id,
)
from utils.helpers import CST
from utils.logger import get_logger


class KnowledgeStore:
    """In-memory knowledge base with alias-based entity resolution.

    Usage::

        store = KnowledgeStore("data/knowledge/kb.json")
        obj = store.resolve_or_create("友宝在线", "company", signal_id="sig_001")
        store.add_relation(obj.id, other_id, "cooperate", signal_id="sig_001")
        store.save()
    """

    def __init__(self, persist_path: str = "data/knowledge/kb.json") -> None:
        self.persist_path = persist_path
        self.logger = get_logger()

        # Core registries
        self._objects: dict[str, KnowledgeObject] = {}   # id → KnowledgeObject
        self._alias_index: dict[str, str] = {}           # alias(lower) → object_id
        self._relations: dict[str, Relation] = {}        # id → Relation

        # Load existing KB
        self._load()

    # ------------------------------------------------------------------
    # Entity Resolution
    # ------------------------------------------------------------------

    def resolve(self, name: str) -> KnowledgeObject | None:
        """Resolve a name/alias to an existing KnowledgeObject."""
        key = name.strip().lower()
        obj_id = self._alias_index.get(key)
        if obj_id:
            return self._objects.get(obj_id)
        return None

    def resolve_or_create(
        self,
        name: str,
        entity_type: str,
        signal_id: str = "",
        industry_role: str = "",
        confidence: int = 60,
    ) -> KnowledgeObject:
        """Resolve mention to existing entity, or create a new one.

        Returns the canonical KnowledgeObject.
        """
        existing = self.resolve(name)
        if existing is not None:
            existing.increment_mentions(signal_id)
            return existing

        # Create new entity
        obj_id = generate_entity_id(entity_type, name)

        # Check if ID collision (different name, same hash — extremely unlikely)
        if obj_id in self._objects:
            existing = self._objects[obj_id]
            existing.add_alias(name)
            self._register_alias(name, obj_id)
            existing.increment_mentions(signal_id)
            return existing

        obj = KnowledgeObject(
            id=obj_id,
            entity_type=entity_type,
            canonical_name=name.strip(),
            industry_role=industry_role,
            confidence=confidence,
            provenance="derived",
            mention_count=1,
            source_signals=[signal_id] if signal_id else [],
        )

        self._objects[obj_id] = obj
        self._register_alias(name, obj_id)

        return obj

    def add_alias(self, entity_id: str, alias: str) -> bool:
        """Add an alias to an existing entity."""
        obj = self._objects.get(entity_id)
        if obj is None:
            return False
        added = obj.add_alias(alias)
        if added:
            self._register_alias(alias, entity_id)
        return added

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    def add_relation(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
        signal_id: str = "",
        confidence: int = 60,
    ) -> Relation | None:
        """Add a relation between two entities. Deduplicates by ID."""
        if from_id not in self._objects or to_id not in self._objects:
            return None

        rel_id = generate_relation_id(from_id, to_id, relation_type)
        if rel_id in self._relations:
            return self._relations[rel_id]

        rel = Relation(
            id=rel_id,
            from_id=from_id,
            to_id=to_id,
            relation_type=relation_type,
            confidence=confidence,
            provenance="derived",
            source_signal=signal_id,
        )
        self._relations[rel_id] = rel
        return rel

    def get_relations(self, entity_id: str) -> list[Relation]:
        """Get all relations involving an entity (as source or target)."""
        return [
            r for r in self._relations.values()
            if r.from_id == entity_id or r.to_id == entity_id
        ]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, entity_id: str) -> KnowledgeObject | None:
        return self._objects.get(entity_id)

    def list_objects(
        self,
        entity_type: str | None = None,
        lifecycle: str | None = None,
        min_mentions: int = 0,
    ) -> list[KnowledgeObject]:
        """List knowledge objects with optional filters."""
        results = list(self._objects.values())
        if entity_type:
            results = [o for o in results if o.entity_type == entity_type]
        if lifecycle:
            results = [o for o in results if o.lifecycle == lifecycle]
        if min_mentions > 0:
            results = [o for o in results if o.mention_count >= min_mentions]
        return sorted(results, key=lambda o: o.mention_count, reverse=True)

    @property
    def object_count(self) -> int:
        return len(self._objects)

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    def stats(self) -> dict:
        """Return KB statistics."""
        by_type: dict[str, int] = {}
        for obj in self._objects.values():
            by_type[obj.entity_type] = by_type.get(obj.entity_type, 0) + 1

        by_role: dict[str, int] = {}
        for obj in self._objects.values():
            if obj.industry_role:
                by_role[obj.industry_role] = by_role.get(obj.industry_role, 0) + 1

        return {
            "total_objects": self.object_count,
            "total_relations": self.relation_count,
            "total_aliases": len(self._alias_index),
            "by_type": by_type,
            "by_role": by_role,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> str | None:
        """Persist KB to JSON file. Returns path or None on failure."""
        try:
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
            data = {
                "version": 1,
                "saved_at": datetime.now(CST).isoformat(timespec="seconds"),
                "objects": [obj.to_dict() for obj in self._objects.values()],
                "relations": [rel.to_dict() for rel in self._relations.values()],
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(
                "[kb] Saved: %d objects, %d relations → %s",
                self.object_count, self.relation_count, self.persist_path,
            )
            return self.persist_path
        except Exception as e:
            self.logger.warning("[kb] Save failed: %s", e)
            return None

    def _load(self) -> None:
        """Load KB from JSON file if it exists."""
        if not os.path.exists(self.persist_path):
            return

        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for obj_data in data.get("objects", []):
                obj = KnowledgeObject(
                    id=obj_data["id"],
                    entity_type=obj_data["entity_type"],
                    canonical_name=obj_data["canonical_name"],
                    aliases=obj_data.get("aliases", []),
                    industry_role=obj_data.get("industry_role", ""),
                    industry_segment=obj_data.get("industry_segment", ""),
                    lifecycle=obj_data.get("lifecycle", "draft"),
                    confidence=obj_data.get("confidence", 50),
                    provenance=obj_data.get("provenance", "derived"),
                    source_signals=obj_data.get("source_signals", []),
                    mention_count=obj_data.get("mention_count", 0),
                    metadata=obj_data.get("metadata", {}),
                    created_at=obj_data.get("created_at", ""),
                    updated_at=obj_data.get("updated_at", ""),
                )
                self._objects[obj.id] = obj
                # Rebuild alias index
                self._register_alias(obj.canonical_name, obj.id)
                for alias in obj.aliases:
                    self._register_alias(alias, obj.id)

            for rel_data in data.get("relations", []):
                rel = Relation(
                    id=rel_data["id"],
                    from_id=rel_data["from_id"],
                    to_id=rel_data["to_id"],
                    relation_type=rel_data["relation_type"],
                    confidence=rel_data.get("confidence", 50),
                    provenance=rel_data.get("provenance", "derived"),
                    source_signal=rel_data.get("source_signal", ""),
                    metadata=rel_data.get("metadata", {}),
                    created_at=rel_data.get("created_at", ""),
                )
                self._relations[rel.id] = rel

            self.logger.info(
                "[kb] Loaded: %d objects, %d relations from %s",
                self.object_count, self.relation_count, self.persist_path,
            )
        except Exception as e:
            self.logger.warning("[kb] Load failed: %s", e)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _register_alias(self, name: str, obj_id: str) -> None:
        """Register a name in the alias index."""
        self._alias_index[name.strip().lower()] = obj_id
