"""Discovery scoring (not editorial quality)."""

from __future__ import annotations

from urllib.parse import urlsplit

from discovery.models import SearchCandidate

_TIER_S_HINTS = (
    "gov.cn",
    "sse.com.cn",
    "szse.cn",
    "cninfo.com.cn",
    "stats.gov.cn",
)
_TIER_A_HINTS = (
    "xinhuanet.com",
    "people.com.cn",
    "36kr.com",
    "caixin.com",
    "yicai.com",
)


def score_candidate(candidate: SearchCandidate) -> float:
    """Heuristic discovery score: higher = more worth fetching."""
    score = 50.0
    host = urlsplit(candidate.url).netloc.lower()
    if any(host.endswith(h) or h in host for h in _TIER_S_HINTS):
        score += 30.0
    elif any(host.endswith(h) or h in host for h in _TIER_A_HINTS):
        score += 18.0
    if candidate.title:
        score += min(10.0, len(candidate.title) / 20.0)
    if candidate.snippet:
        score += 5.0
    if candidate.rank:
        score += max(0.0, 11.0 - float(candidate.rank))
    query = (candidate.query or "").strip()
    if query and query in (candidate.title or ""):
        score += 8.0
    elif query and query in (candidate.snippet or ""):
        score += 4.0
    return round(score, 2)
