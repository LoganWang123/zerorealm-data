"""Semantic Search Engine — hybrid keyword + vector search over Knowledge Base.

Aligned with Execution Architecture §1.2 (Experience Context — AI Search):
- Hybrid search: keyword matching + cosine similarity
- Returns ranked KnowledgeObjects with relevance scores
- Supports entity type / role filtering

Usage::

    from knowledge.search import SearchEngine

    engine = SearchEngine()
    results = engine.search("友宝融资")
    for hit in results:
        print(hit.object.canonical_name, hit.score)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge import KnowledgeObject
from knowledge.store import KnowledgeStore
from storage.vectors import VectorStore, SearchResult as VectorHit, cosine_similarity
from utils.logger import get_logger


@dataclass
class SearchHit:
    """A single search result combining KB object + relevance score."""

    object: KnowledgeObject
    score: float                    # combined relevance (0~1)
    match_type: str = ""            # "keyword" / "vector" / "hybrid"
    matched_text: str = ""          # the text chunk that matched

    def to_dict(self) -> dict:
        return {
            "id": self.object.id,
            "name": self.object.canonical_name,
            "type": self.object.entity_type,
            "role": self.object.industry_role,
            "score": round(self.score, 4),
            "match_type": self.match_type,
            "matched_text": self.matched_text[:200],
            "mention_count": self.object.mention_count,
            "aliases": self.object.aliases[:5],
        }


@dataclass
class SearchResponse:
    """Aggregated search response."""

    query: str
    hits: list[SearchHit] = field(default_factory=list)
    total: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total": self.total,
            "latency_ms": self.latency_ms,
            "hits": [h.to_dict() for h in self.hits],
        }


class SearchEngine:
    """Hybrid search over KnowledgeStore + VectorStore.

    Search strategy:
    1. Keyword: exact/fuzzy match on canonical_name + aliases
    2. Vector: cosine similarity on embeddings (when available)
    3. Hybrid: weighted combination (keyword 0.4 + vector 0.6)
    """

    def __init__(
        self,
        kb: KnowledgeStore | None = None,
        vs: VectorStore | None = None,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> None:
        self.kb = kb or KnowledgeStore()
        self.vs = vs or VectorStore()
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
        self.logger = get_logger()

    def search(
        self,
        query: str,
        top_k: int = 10,
        entity_type: str | None = None,
        query_embedding: list[float] | None = None,
    ) -> SearchResponse:
        """Execute hybrid search.

        Parameters
        ----------
        query:
            Natural language query text.
        top_k:
            Max results.
        entity_type:
            Filter by entity type (company / product / technology / ...).
        query_embedding:
            Pre-computed query embedding. If None, only keyword search is used.
        """
        import time
        start = time.time()

        # Phase 1: Keyword search
        keyword_hits = self._keyword_search(query, entity_type)

        # Phase 2: Vector search (if embedding available)
        vector_hits: dict[str, tuple[float, str]] = {}  # object_id → (score, text)
        if query_embedding and self.vs.count > 0:
            vector_hits = self._vector_search(query_embedding, entity_type, top_k * 2)

        # Phase 3: Merge & rank
        merged = self._merge_results(keyword_hits, vector_hits, query)

        # Sort by score descending
        merged.sort(key=lambda h: h.score, reverse=True)
        hits = merged[:top_k]

        latency_ms = int((time.time() - start) * 1000)

        return SearchResponse(
            query=query,
            hits=hits,
            total=len(hits),
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # Keyword Search
    # ------------------------------------------------------------------

    def _keyword_search(
        self,
        query: str,
        entity_type: str | None = None,
    ) -> dict[str, float]:
        """Match query against canonical_name + aliases.

        Returns {object_id: score} where score ∈ [0, 1].
        """
        query_lower = query.strip().lower()
        query_tokens = set(query_lower)
        scores: dict[str, float] = {}

        objects = self.kb.list_objects(entity_type=entity_type)

        for obj in objects:
            score = self._match_score(query_lower, obj)
            if score > 0:
                scores[obj.id] = score

        return scores

    def _match_score(self, query: str, obj: KnowledgeObject) -> float:
        """Compute keyword match score between query and object."""
        name = obj.canonical_name.lower()

        # Exact match
        if query == name:
            return 1.0

        # Query contains name or name contains query
        if name in query:
            return 0.9
        if query in name:
            return 0.85

        # Alias match
        for alias in obj.aliases:
            alias_lower = alias.lower()
            if query == alias_lower:
                return 0.95
            if alias_lower in query:
                return 0.8
            if query in alias_lower:
                return 0.75

        # Character overlap (Jaccard-like for Chinese)
        query_chars = set(query)
        name_chars = set(name)
        if not query_chars or not name_chars:
            return 0.0
        intersection = query_chars & name_chars
        union = query_chars | name_chars
        jaccard = len(intersection) / len(union)

        # Only count if overlap is significant
        if jaccard >= 0.4:
            return jaccard * 0.7  # scale down vs exact matches

        return 0.0

    # ------------------------------------------------------------------
    # Vector Search
    # ------------------------------------------------------------------

    def _vector_search(
        self,
        query_embedding: list[float],
        entity_type: str | None,
        limit: int,
    ) -> dict[str, tuple[float, str]]:
        """Vector similarity search.

        Returns {object_id: (score, matched_text)}.
        """
        results = self.vs.search(
            query_embedding=query_embedding,
            top_k=limit,
            object_type="knowledge_object" if entity_type else None,
            threshold=0.3,
        )

        hits: dict[str, tuple[float, str]] = {}
        for hit in results:
            obj_id = hit.object_id
            # Keep best score per object
            if obj_id not in hits or hit.score > hits[obj_id][0]:
                hits[obj_id] = (hit.score, hit.text)

        return hits

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def _merge_results(
        self,
        keyword_scores: dict[str, float],
        vector_scores: dict[str, tuple[float, str]],
        query: str,
    ) -> list[SearchHit]:
        """Merge keyword and vector results into ranked SearchHits."""
        all_ids = set(keyword_scores.keys()) | set(vector_scores.keys())
        hits: list[SearchHit] = []

        for obj_id in all_ids:
            obj = self.kb.get(obj_id)
            if obj is None:
                continue

            kw_score = keyword_scores.get(obj_id, 0.0)
            vec_score, vec_text = vector_scores.get(obj_id, (0.0, ""))

            # Determine match type and combined score
            if kw_score > 0 and vec_score > 0:
                combined = kw_score * self.keyword_weight + vec_score * self.vector_weight
                match_type = "hybrid"
                matched_text = vec_text or obj.canonical_name
            elif kw_score > 0:
                combined = kw_score
                match_type = "keyword"
                matched_text = obj.canonical_name
            else:
                combined = vec_score
                match_type = "vector"
                matched_text = vec_text

            hits.append(SearchHit(
                object=obj,
                score=combined,
                match_type=match_type,
                matched_text=matched_text,
            ))

        return hits

    # ------------------------------------------------------------------
    # Indexing helpers
    # ------------------------------------------------------------------

    def index_object(self, obj: KnowledgeObject, embedding: list[float]) -> None:
        """Add a KnowledgeObject's embedding to the vector store."""
        text = f"{obj.canonical_name} {' '.join(obj.aliases[:5])} {obj.industry_role}"
        self.vs.add(
            object_id=obj.id,
            object_type="knowledge_object",
            text=text.strip(),
            embedding=embedding,
            model="",
        )

    def index_signal(self, signal_id: str, title: str, summary: str, embedding: list[float]) -> None:
        """Add a signal's embedding to the vector store."""
        text = f"{title} {summary}".strip()
        self.vs.add(
            object_id=signal_id,
            object_type="signal",
            text=text,
            embedding=embedding,
        )
