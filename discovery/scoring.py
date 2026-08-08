"""Discovery scoring = research priority (not editorial / publish score)."""

from __future__ import annotations

from dataclasses import dataclass

from discovery.freshness import freshness_score
from discovery.models import SearchCandidate
from discovery.source_quality import (
    TIER_SCORE,
    SourceClassification,
    SourceTier,
    classify_source,
)


@dataclass(frozen=True)
class DiscoveryScoreBreakdown:
    discovery_score: float
    relevance: float
    source_tier: float
    freshness: float
    topic_match: float
    company_match: float
    duplicate_penalty: float

    def to_dict(self) -> dict:
        return {
            "discovery_score": self.discovery_score,
            "relevance": self.relevance,
            "source_tier": self.source_tier,
            "freshness": self.freshness,
            "topic_match": self.topic_match,
            "company_match": self.company_match,
            "duplicate_penalty": self.duplicate_penalty,
        }


def _text_blob(candidate: SearchCandidate) -> str:
    return f"{candidate.title or ''}\n{candidate.snippet or ''}"


def score_candidate(
    candidate: SearchCandidate,
    *,
    classification: SourceClassification | None = None,
    published_at: str | None = None,
    intent: str = "research",
    freshness_window: str | None = None,
    topic_terms: list[str] | None = None,
    company_terms: list[str] | None = None,
    duplicate: bool = False,
    syndication_penalty: float = 0.0,
) -> float:
    """Backward-compatible score float (higher = more worth prioritizing)."""
    return score_candidate_breakdown(
        candidate,
        classification=classification,
        published_at=published_at,
        intent=intent,
        freshness_window=freshness_window,
        topic_terms=topic_terms,
        company_terms=company_terms,
        duplicate=duplicate,
        syndication_penalty=syndication_penalty,
    ).discovery_score


def score_candidate_breakdown(
    candidate: SearchCandidate,
    *,
    classification: SourceClassification | None = None,
    published_at: str | None = None,
    intent: str = "research",
    freshness_window: str | None = None,
    topic_terms: list[str] | None = None,
    company_terms: list[str] | None = None,
    duplicate: bool = False,
    syndication_penalty: float = 0.0,
) -> DiscoveryScoreBreakdown:
    """Compose relevance + source_tier + freshness + matches − duplicate/syndication."""
    clf = classification or classify_source(
        candidate.url,
        title=candidate.title,
        publisher="",
    )
    tier = clf.source_tier if isinstance(clf.source_tier, SourceTier) else SourceTier.C
    tier_points = TIER_SCORE.get(tier, 0.0)

    relevance = 40.0
    if candidate.rank:
        relevance += max(0.0, 11.0 - float(candidate.rank))
    if candidate.title:
        relevance += min(6.0, len(candidate.title) / 30.0)
    if candidate.snippet:
        relevance += 3.0

    query = (candidate.query or "").strip()
    blob = _text_blob(candidate)
    topic_points = 0.0
    if query and query in (candidate.title or ""):
        topic_points += 8.0
    elif query and query in blob:
        topic_points += 4.0
    for term in topic_terms or []:
        t = str(term).strip()
        if t and t in blob:
            topic_points += 2.0
    topic_points = min(12.0, topic_points)

    company_points = 0.0
    for term in company_terms or []:
        t = str(term).strip()
        if t and t in blob:
            company_points += 4.0
    company_points = min(12.0, company_points)

    fresh_points = freshness_score(
        published_at,
        intent=intent,
        freshness_window=freshness_window,
    )
    dup_penalty = (15.0 if duplicate else 0.0) + float(syndication_penalty or 0.0)

    total = (
        relevance
        + tier_points
        + fresh_points
        + topic_points
        + company_points
        - dup_penalty
    )
    return DiscoveryScoreBreakdown(
        discovery_score=round(total, 2),
        relevance=round(relevance, 2),
        source_tier=round(tier_points, 2),
        freshness=round(fresh_points, 2),
        topic_match=round(topic_points, 2),
        company_match=round(company_points, 2),
        duplicate_penalty=round(dup_penalty, 2),
    )
