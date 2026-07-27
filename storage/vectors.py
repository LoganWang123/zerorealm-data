"""Vector Store — local in-memory vector index with cosine similarity.

M3/M4: pure-Python local index (JSON persistence, brute-force search).
M5+: migrate to Supabase pgvector for production scale.

Usage::

    from storage.vectors import VectorStore

    vs = VectorStore("data/knowledge/vectors.json")
    vs.add("obj_001", "knowledge_object", "友宝完成C轮融资", [0.1, 0.2, ...])
    results = vs.search([0.1, 0.2, ...], top_k=5)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime

from utils.helpers import CST
from utils.logger import get_logger


@dataclass
class VectorRecord:
    """A single embedding record."""

    id: str
    object_id: str
    object_type: str          # knowledge_object / signal / document
    chunk_text: str
    embedding: list[float]
    chunk_index: int = 0
    model: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "object_id": self.object_id,
            "object_type": self.object_type,
            "chunk_text": self.chunk_text,
            "embedding": self.embedding,
            "chunk_index": self.chunk_index,
            "model": self.model,
            "created_at": self.created_at,
        }


@dataclass
class SearchResult:
    """A single search hit."""

    record: VectorRecord
    score: float              # cosine similarity (0~1)

    @property
    def object_id(self) -> str:
        return self.record.object_id

    @property
    def text(self) -> str:
        return self.record.chunk_text


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def generate_vector_id(object_id: str, chunk_index: int = 0) -> str:
    """Deterministic vector ID."""
    key = f"{object_id}:{chunk_index}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class VectorStore:
    """Local in-memory vector store with brute-force cosine search.

    Suitable for <10k vectors. For production scale, use pgvector.
    """

    def __init__(self, persist_path: str = "data/knowledge/vectors.json") -> None:
        self.persist_path = persist_path
        self.logger = get_logger()
        self._records: dict[str, VectorRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(
        self,
        object_id: str,
        object_type: str,
        text: str,
        embedding: list[float],
        chunk_index: int = 0,
        model: str = "",
    ) -> VectorRecord:
        """Add or update a vector record."""
        vec_id = generate_vector_id(object_id, chunk_index)
        record = VectorRecord(
            id=vec_id,
            object_id=object_id,
            object_type=object_type,
            chunk_text=text,
            embedding=embedding,
            chunk_index=chunk_index,
            model=model,
        )
        self._records[vec_id] = record
        return record

    def add_batch(
        self,
        items: list[dict],
    ) -> int:
        """Batch add vectors. Each item: {object_id, object_type, text, embedding, ...}"""
        count = 0
        for item in items:
            self.add(
                object_id=item["object_id"],
                object_type=item.get("object_type", "signal"),
                text=item["text"],
                embedding=item["embedding"],
                chunk_index=item.get("chunk_index", 0),
                model=item.get("model", ""),
            )
            count += 1
        return count

    def remove(self, object_id: str) -> int:
        """Remove all vectors for an object. Returns count removed."""
        to_remove = [
            vid for vid, r in self._records.items()
            if r.object_id == object_id
        ]
        for vid in to_remove:
            del self._records[vid]
        return len(to_remove)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        object_type: str | None = None,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """Brute-force cosine similarity search.

        Parameters
        ----------
        query_embedding:
            The query vector.
        top_k:
            Max results to return.
        object_type:
            Filter by object type (optional).
        threshold:
            Minimum similarity score (optional).
        """
        candidates = self._records.values()
        if object_type:
            candidates = [r for r in candidates if r.object_type == object_type]

        scored: list[SearchResult] = []
        for record in candidates:
            score = cosine_similarity(query_embedding, record.embedding)
            if score >= threshold:
                scored.append(SearchResult(record=record, score=score))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, object_id: str) -> list[VectorRecord]:
        """Get all vector records for an object."""
        return [r for r in self._records.values() if r.object_id == object_id]

    @property
    def count(self) -> int:
        return len(self._records)

    def stats(self) -> dict:
        by_type: dict[str, int] = {}
        for r in self._records.values():
            by_type[r.object_type] = by_type.get(r.object_type, 0) + 1
        return {"total_vectors": self.count, "by_type": by_type}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> str | None:
        """Persist to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
            data = {
                "version": 1,
                "count": self.count,
                "records": [r.to_dict() for r in self._records.values()],
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self.logger.info("[vectors] Saved %d vectors → %s", self.count, self.persist_path)
            return self.persist_path
        except Exception as e:
            self.logger.warning("[vectors] Save failed: %s", e)
            return None

    def _load(self) -> None:
        """Load from JSON file if exists."""
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for rec in data.get("records", []):
                record = VectorRecord(
                    id=rec["id"],
                    object_id=rec["object_id"],
                    object_type=rec["object_type"],
                    chunk_text=rec["chunk_text"],
                    embedding=rec["embedding"],
                    chunk_index=rec.get("chunk_index", 0),
                    model=rec.get("model", ""),
                    created_at=rec.get("created_at", ""),
                )
                self._records[record.id] = record
            self.logger.info("[vectors] Loaded %d vectors from %s", self.count, self.persist_path)
        except Exception as e:
            self.logger.warning("[vectors] Load failed: %s", e)
