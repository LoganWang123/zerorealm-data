"""URL normalization and candidate dedupe."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from discovery.models import SearchCandidate

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = frozenset(
    {
        "spm",
        "from",
        "source",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "ved",
        "si",
    }
)


def strip_tracking_params(url: str) -> str:
    """Drop tracking query params / fragment but keep host as-is (including www)."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    path = parts.path or "/"
    query_pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith(_TRACKING_PREFIXES) or lower in _TRACKING_KEYS:
            continue
        query_pairs.append((key, value))
    query = urlencode(query_pairs, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def normalize_url(url: str) -> str:
    """Canonicalize URL for dedupe (drop tracking params / fragments / www.)."""
    raw = strip_tracking_params(url)
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def dedupe_candidates(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
    """Keep the best-ranked candidate per canonical URL (preserve fetchable URL)."""
    best: dict[str, SearchCandidate] = {}
    order: list[str] = []
    for cand in candidates:
        key = normalize_url(cand.url)
        if not key:
            continue
        fetch_url = strip_tracking_params(cand.url) or cand.url
        if key not in best:
            best[key] = SearchCandidate(
                provider=cand.provider,
                query=cand.query,
                title=cand.title,
                url=fetch_url,
                snippet=cand.snippet,
                provider_content=cand.provider_content,
                rank=cand.rank,
                discovered_at=cand.discovered_at,
                language=cand.language,
                evidence_eligible=False,
            )
            order.append(key)
            continue
        existing = best[key]
        if cand.rank and (not existing.rank or cand.rank < existing.rank):
            best[key] = SearchCandidate(
                provider=cand.provider,
                query=cand.query,
                title=cand.title or existing.title,
                url=fetch_url or existing.url,
                snippet=cand.snippet or existing.snippet,
                provider_content=cand.provider_content or existing.provider_content,
                rank=cand.rank,
                discovered_at=cand.discovered_at or existing.discovered_at,
                language=cand.language or existing.language,
                evidence_eligible=False,
            )
    return [best[key] for key in order]
