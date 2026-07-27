"""Semantic Dedup — group near-duplicate signals by title/content similarity.

Aligned with Execution Architecture §1.2 (Understand Context):
- dedup_group_id: signals about the same real-world event get the same ID
- Uses TF-IDF + cosine similarity (zero external dependency, zero API cost)
- M3+: upgrade to Embedding-based similarity when Supabase pgvector is available

Strategy:
1. Vectorize titles via TF-IDF (char n-grams, works well for Chinese)
2. Compute pairwise cosine similarity
3. Union-Find clustering with threshold
4. Assign dedup_group_id to each cluster
"""

import hashlib
import re
from dataclasses import dataclass, field

from crawlers.base import RawItem
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SIMILARITY_THRESHOLD = 0.6   # cosine similarity ≥ this → same group
MIN_TITLE_LENGTH = 6                  # skip very short titles


# ---------------------------------------------------------------------------
# TF-IDF Vectorizer (pure Python, no sklearn dependency)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Character bigram tokenization (works for Chinese without jieba)."""
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text.lower())
    if len(text) < 2:
        return [text] if text else []
    return [text[i:i + 2] for i in range(len(text) - 1)]


class TfidfVectorizer:
    """Minimal TF-IDF vectorizer using character bigrams."""

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self._doc_count = 0

    def fit(self, documents: list[str]) -> "TfidfVectorizer":
        """Build vocabulary and IDF from documents."""
        import math

        self._doc_count = len(documents)
        df: dict[str, int] = {}

        for doc in documents:
            tokens = set(_tokenize(doc))
            for token in tokens:
                df[token] = df.get(token, 0) + 1

        self.vocab = {token: i for i, token in enumerate(sorted(df.keys()))}
        self.idf = {
            token: math.log((self._doc_count + 1) / (count + 1)) + 1
            for token, count in df.items()
        }
        return self

    def transform(self, text: str) -> dict[int, float]:
        """Return sparse TF-IDF vector as {index: weight}."""
        tokens = _tokenize(text)
        if not tokens:
            return {}

        # Term frequency
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        # TF-IDF
        vec: dict[int, float] = {}
        for token, count in tf.items():
            if token in self.vocab:
                idx = self.vocab[token]
                vec[idx] = (count / len(tokens)) * self.idf.get(token, 1.0)

        return vec


def cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not a or not b:
        return 0.0

    # Dot product (iterate over smaller dict)
    if len(a) > len(b):
        a, b = b, a
    dot = sum(a[k] * b[k] for k in a if k in b)

    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------


class UnionFind:
    """Simple Union-Find for clustering."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


# ---------------------------------------------------------------------------
# Core clustering
# ---------------------------------------------------------------------------


@dataclass
class DedupGroup:
    """A cluster of near-duplicate items."""

    group_id: str
    item_ids: list[str] = field(default_factory=list)
    representative_title: str = ""
    size: int = 0


def cluster_duplicates(
    items: list[RawItem],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[DedupGroup]:
    """Cluster items by title similarity using TF-IDF + cosine + Union-Find.

    Returns list of DedupGroup (only groups with size ≥ 2).
    """
    if len(items) < 2:
        return []

    # Build TF-IDF vectors from titles
    titles = [item.title for item in items]
    vectorizer = TfidfVectorizer().fit(titles)
    vectors = [vectorizer.transform(t) for t in titles]

    # Pairwise similarity + Union-Find
    uf = UnionFind(len(items))
    for i in range(len(items)):
        if len(titles[i]) < MIN_TITLE_LENGTH:
            continue
        for j in range(i + 1, len(items)):
            if len(titles[j]) < MIN_TITLE_LENGTH:
                continue
            sim = cosine_similarity(vectors[i], vectors[j])
            if sim >= threshold:
                uf.union(i, j)

    # Collect clusters
    clusters: dict[int, list[int]] = {}
    for i in range(len(items)):
        root = uf.find(i)
        clusters.setdefault(root, []).append(i)

    # Build DedupGroups (only multi-item clusters)
    groups: list[DedupGroup] = []
    for root, indices in clusters.items():
        if len(indices) < 2:
            continue

        # Group ID: deterministic hash of sorted item IDs
        member_ids = sorted(items[i].id for i in indices)
        group_id = hashlib.sha256("|".join(member_ids).encode()).hexdigest()[:16]

        # Representative: longest title (most informative)
        rep_idx = max(indices, key=lambda i: len(titles[i]))

        groups.append(DedupGroup(
            group_id=group_id,
            item_ids=[items[i].id for i in indices],
            representative_title=titles[rep_idx],
            size=len(indices),
        ))

    return groups


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------


def apply_semantic_dedup(
    items: list[RawItem],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[list[RawItem], list[DedupGroup]]:
    """Assign dedup_group_id to items, return (items, groups).

    - Items in a cluster get ``metadata["dedup_group_id"]`` and
      ``metadata["dedup_role"]`` = "representative" | "duplicate".
    - Items not in any cluster are unchanged.
    - All items are returned (no filtering); downstream decides what to do.
    """
    logger = get_logger()

    if len(items) < 2:
        return items, []

    groups = cluster_duplicates(items, threshold)

    # Build lookup: item_id → (group_id, is_representative)
    item_group: dict[str, tuple[str, bool]] = {}
    for group in groups:
        rep_title = group.representative_title
        for item_id in group.item_ids:
            # Find the item to check if it's the representative
            is_rep = False
            for item in items:
                if item.id == item_id and item.title == rep_title:
                    is_rep = True
                    break
            item_group[item_id] = (group.group_id, is_rep)

    # Annotate items
    for item in items:
        if item.id in item_group:
            gid, is_rep = item_group[item.id]
            item.metadata["dedup_group_id"] = gid
            item.metadata["dedup_role"] = "representative" if is_rep else "duplicate"

    dup_count = sum(1 for i in items if i.metadata.get("dedup_role") == "duplicate")
    logger.info(
        "[semantic_dedup] %d items → %d groups, %d duplicates flagged",
        len(items),
        len(groups),
        dup_count,
    )

    return items, groups


def filter_duplicates_semantic(
    items: list[RawItem],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[list[RawItem], int]:
    """Convenience: cluster + keep only representatives.

    Returns (deduplicated_items, removed_count).
    """
    items, groups = apply_semantic_dedup(items, threshold)
    kept = [i for i in items if i.metadata.get("dedup_role") != "duplicate"]
    removed = len(items) - len(kept)
    return kept, removed
