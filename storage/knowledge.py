"""Knowledge Repository — persist KnowledgeObjects and Relations to Supabase.

Aligned with Execution Architecture §2.5 (knowledge_objects / relations tables).
Falls back to no-op when Supabase is not configured.

Usage::

    repo = KnowledgeRepository()
    repo.save_object(obj)
    repo.save_relation(rel)
    repo.find_by_name("友宝")
"""

from __future__ import annotations

from knowledge import KnowledgeObject, Relation
from storage.db import get_client, is_db_available
from utils.logger import get_logger


class KnowledgeRepository:
    """Persist knowledge objects and relations to Supabase."""

    def __init__(self) -> None:
        self.logger = get_logger()
        self._available = is_db_available()

    # ------------------------------------------------------------------
    # KnowledgeObject CRUD
    # ------------------------------------------------------------------

    def save_object(self, obj: KnowledgeObject) -> bool:
        """Upsert a single KnowledgeObject."""
        if not self._available:
            return False
        try:
            get_client().table("knowledge_objects").upsert(
                self._obj_to_row(obj), on_conflict="id"
            ).execute()
            return True
        except Exception as e:
            self.logger.warning("[db] save_object failed: %s", e)
            return False

    def save_objects_batch(self, objects: list[KnowledgeObject]) -> int:
        """Batch upsert KnowledgeObjects. Returns count saved."""
        if not self._available or not objects:
            return 0
        try:
            rows = [self._obj_to_row(o) for o in objects]
            chunk_size = 50
            saved = 0
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                get_client().table("knowledge_objects").upsert(
                    chunk, on_conflict="id"
                ).execute()
                saved += len(chunk)
            self.logger.info("[db] Saved %d knowledge objects", saved)
            return saved
        except Exception as e:
            self.logger.warning("[db] save_objects_batch failed: %s", e)
            return 0

    def find_by_name(self, name: str) -> KnowledgeObject | None:
        """Find a KnowledgeObject by canonical_name or alias."""
        if not self._available:
            return None
        try:
            # Try canonical_name first
            result = (
                get_client()
                .table("knowledge_objects")
                .select("*")
                .eq("canonical_name", name)
                .limit(1)
                .execute()
            )
            if result.data:
                return self._row_to_obj(result.data[0])

            # Try aliases (JSONB contains)
            result = (
                get_client()
                .table("knowledge_objects")
                .select("*")
                .contains("aliases", [name])
                .limit(1)
                .execute()
            )
            if result.data:
                return self._row_to_obj(result.data[0])

            return None
        except Exception as e:
            self.logger.warning("[db] find_by_name failed: %s", e)
            return None

    def list_objects(
        self,
        entity_type: str | None = None,
        lifecycle: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeObject]:
        """List knowledge objects with optional filters."""
        if not self._available:
            return []
        try:
            query = get_client().table("knowledge_objects").select("*")
            if entity_type:
                query = query.eq("entity_type", entity_type)
            if lifecycle:
                query = query.eq("lifecycle", lifecycle)
            query = query.order("mention_count", desc=True).limit(limit)
            result = query.execute()
            return [self._row_to_obj(row) for row in result.data]
        except Exception as e:
            self.logger.warning("[db] list_objects failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Relation CRUD
    # ------------------------------------------------------------------

    def save_relation(self, rel: Relation) -> bool:
        """Upsert a single Relation."""
        if not self._available:
            return False
        try:
            get_client().table("relations").upsert(
                self._rel_to_row(rel), on_conflict="id"
            ).execute()
            return True
        except Exception as e:
            self.logger.warning("[db] save_relation failed: %s", e)
            return False

    def get_relations(self, entity_id: str) -> list[Relation]:
        """Get all relations involving an entity."""
        if not self._available:
            return []
        try:
            # Relations where entity is source
            result_from = (
                get_client()
                .table("relations")
                .select("*")
                .eq("from_id", entity_id)
                .execute()
            )
            # Relations where entity is target
            result_to = (
                get_client()
                .table("relations")
                .select("*")
                .eq("to_id", entity_id)
                .execute()
            )
            rows = (result_from.data or []) + (result_to.data or [])
            return [self._row_to_rel(row) for row in rows]
        except Exception as e:
            self.logger.warning("[db] get_relations failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _obj_to_row(obj: KnowledgeObject) -> dict:
        return {
            "id": obj.id,
            "tenant_id": "default",
            "entity_type": obj.entity_type,
            "canonical_name": obj.canonical_name,
            "aliases": obj.aliases,
            "industry_role": obj.industry_role or None,
            "industry_segment": obj.industry_segment or None,
            "lifecycle": obj.lifecycle,
            "confidence": obj.confidence,
            "provenance": obj.provenance,
            "mention_count": obj.mention_count,
            "source_signals": obj.source_signals[-20:],
            "metadata": obj.metadata,
        }

    @staticmethod
    def _row_to_obj(row: dict) -> KnowledgeObject:
        return KnowledgeObject(
            id=row["id"],
            entity_type=row["entity_type"],
            canonical_name=row["canonical_name"],
            aliases=row.get("aliases", []),
            industry_role=row.get("industry_role", ""),
            industry_segment=row.get("industry_segment", ""),
            lifecycle=row.get("lifecycle", "draft"),
            confidence=row.get("confidence", 50),
            provenance=row.get("provenance", "derived"),
            source_signals=row.get("source_signals", []),
            mention_count=row.get("mention_count", 0),
            metadata=row.get("metadata", {}),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    @staticmethod
    def _rel_to_row(rel: Relation) -> dict:
        return {
            "id": rel.id,
            "tenant_id": "default",
            "from_id": rel.from_id,
            "to_id": rel.to_id,
            "relation_type": rel.relation_type,
            "confidence": rel.confidence,
            "provenance": rel.provenance,
            "source_signal": rel.source_signal or None,
            "metadata": rel.metadata,
        }

    @staticmethod
    def _row_to_rel(row: dict) -> Relation:
        return Relation(
            id=row["id"],
            from_id=row["from_id"],
            to_id=row["to_id"],
            relation_type=row["relation_type"],
            confidence=row.get("confidence", 50),
            provenance=row.get("provenance", "derived"),
            source_signal=row.get("source_signal", ""),
            metadata=row.get("metadata", {}),
            created_at=row.get("created_at", ""),
        )
