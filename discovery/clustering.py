"""Light syndication / duplicate clustering for Discovery ranking."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from discovery.models import SearchCandidate
from discovery.source_quality import SourceTier, classify_source


class SourceRole(str, Enum):
    ORIGINAL = "original"
    SECONDARY_REPORT = "secondary_report"
    SYNDICATED_COPY = "syndicated_copy"
    UNIQUE = "unique"


def normalize_title(title: str) -> str:
    text = (title or "").lower().strip()
    text = re.sub(r"[\s\-_|·•,，。！？!?:：；;（）()【】\[\]《》\"'“”‘’]+", "", text)
    return text


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # token Jaccard on character bigrams for CJK-friendly similarity
    def grams(s: str) -> set[str]:
        if len(s) < 2:
            return {s}
        return {s[i : i + 2] for i in range(len(s) - 1)}

    ga, gb = grams(na), grams(nb)
    inter = len(ga & gb)
    union = len(ga | gb) or 1
    return inter / union


def content_fingerprint(text: str) -> str:
    body = re.sub(r"\s+", "", (text or "").strip())
    if not body:
        return ""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


def make_cluster_id(*, title: str, published_at: str | None = None) -> str:
    key = f"{normalize_title(title)}|{published_at or ''}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"cluster-{digest}"


@dataclass
class ClusterAssignment:
    source_cluster_id: str
    source_role: SourceRole
    syndication_penalty: float

    def to_dict(self) -> dict:
        return {
            "source_cluster_id": self.source_cluster_id,
            "source_role": self.source_role.value,
            "syndication_penalty": self.syndication_penalty,
        }


def assign_clusters(
    candidates: list[SearchCandidate],
    *,
    published_at_by_url: dict[str, str | None] | None = None,
    fingerprints_by_url: dict[str, str] | None = None,
) -> dict[str, ClusterAssignment]:
    """Group near-duplicate titles; prefer official / higher-tier as original."""
    published_at_by_url = published_at_by_url or {}
    fingerprints_by_url = fingerprints_by_url or {}
    assignments: dict[str, ClusterAssignment] = {}
    groups: list[list[SearchCandidate]] = []

    for cand in candidates:
        placed = False
        for group in groups:
            anchor = group[0]
            sim = title_similarity(cand.title, anchor.title)
            same_fp = False
            fp_a = fingerprints_by_url.get(cand.url, "")
            fp_b = fingerprints_by_url.get(anchor.url, "")
            if fp_a and fp_b and fp_a == fp_b:
                same_fp = True
            pub_a = published_at_by_url.get(cand.url)
            pub_b = published_at_by_url.get(anchor.url)
            same_day = bool(pub_a and pub_b and pub_a[:10] == pub_b[:10])
            if sim >= 0.82 or same_fp or (sim >= 0.7 and same_day):
                group.append(cand)
                placed = True
                break
        if not placed:
            groups.append([cand])

    for group in groups:
        if len(group) == 1:
            cand = group[0]
            pub = published_at_by_url.get(cand.url)
            assignments[cand.url] = ClusterAssignment(
                source_cluster_id=make_cluster_id(title=cand.title, published_at=pub),
                source_role=SourceRole.UNIQUE,
                syndication_penalty=0.0,
            )
            continue

        ranked = sorted(
            group,
            key=lambda c: (
                0 if classify_source(c.url, title=c.title).is_official else 1,
                {"S": 0, "A": 1, "B": 2, "C": 3}.get(
                    classify_source(c.url, title=c.title).source_tier.value, 9
                ),
                c.rank or 99,
            ),
        )
        pub = published_at_by_url.get(ranked[0].url)
        cluster_id = make_cluster_id(title=ranked[0].title, published_at=pub)
        for idx, cand in enumerate(ranked):
            clf = classify_source(cand.url, title=cand.title)
            if idx == 0:
                role = SourceRole.ORIGINAL
                penalty = 0.0
            elif clf.source_tier in {SourceTier.C} or clf.source_type.value == "aggregator":
                role = SourceRole.SYNDICATED_COPY
                penalty = 20.0
            else:
                role = SourceRole.SECONDARY_REPORT
                penalty = 10.0
            assignments[cand.url] = ClusterAssignment(
                source_cluster_id=cluster_id,
                source_role=role,
                syndication_penalty=penalty,
            )
    return assignments
