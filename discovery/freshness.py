"""Freshness scoring for Discovery ranking (not evidence validity)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Intent → preferred freshness half-life (days). Older still allowed; score drops.
_INTENT_HALF_LIFE_DAYS = {
    "daily": 2.0,
    "insight": 14.0,
    "research": 180.0,
}


def parse_published_at(value: Any) -> datetime | None:
    """Parse a published_at value. Never invent 'today' for missing dates."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "null", "none", "n/a"}:
        return None
    # Normalize Zulu
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
            try:
                dt = datetime.strptime(text[:10] if fmt.startswith("%Y-%") else text, fmt)
                break
            except ValueError:
                dt = None
        else:
            return None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_freshness_window(window: str | None) -> float | None:
    """Parse config window like 24h / 48h / 7d / 30d into days."""
    if not window:
        return None
    raw = str(window).strip().lower()
    if not raw or raw in {"none", "null", "unlimited", "any"}:
        return None
    try:
        if raw.endswith("h"):
            return float(raw[:-1]) / 24.0
        if raw.endswith("d"):
            return float(raw[:-1])
        if raw.endswith("m"):
            return float(raw[:-1]) * 30.0
        if raw.endswith("y"):
            return float(raw[:-1]) * 365.0
        return float(raw)
    except ValueError:
        return None


def resolve_discovery_published_at(
    published_at: str | None,
    *,
    crawled_at: str | None = None,
    discovered_at: str | None = None,
) -> str | None:
    """Normalize page publish time for Discovery.

    Never invent today. If the crawler filled ``published_at`` with crawl/discover
    time (common when the page has no date), treat it as unknown/null.
    """
    del discovered_at  # explicitly unused — must never substitute for published_at
    pub = parse_published_at(published_at)
    if pub is None:
        return None
    crawl = parse_published_at(crawled_at)
    if crawl is not None and abs((pub - crawl).total_seconds()) < 120:
        return None
    # Return a stable ISO string without inventing timezone changes beyond parse.
    text = str(published_at or "").strip()
    return text or None


def age_days(published_at: str | None, *, now: datetime | None = None) -> float | None:
    dt = parse_published_at(published_at)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    delta = ref - dt.astimezone(timezone.utc)
    return max(0.0, delta.total_seconds() / 86400.0)


def freshness_score(
    published_at: str | None,
    *,
    intent: str = "research",
    freshness_window: str | None = None,
    now: datetime | None = None,
) -> float:
    """Return 0..20 ranking boost. Unknown date → safe mid/low fallback (not today).

    Freshness affects priority only — never REJECTED by age alone.
    """
    age = age_days(published_at, now=now)
    if age is None:
        # Safe fallback: do not assume "today"; modest neutral score.
        return 5.0

    half_life = _INTENT_HALF_LIFE_DAYS.get((intent or "research").lower(), 180.0)
    window_days = parse_freshness_window(freshness_window)
    if window_days is not None and window_days > 0:
        # Prefer content inside the intent window; outside still scores but lower.
        if age <= window_days:
            return round(20.0 * (1.0 - (age / (window_days * 2.0))), 2)
        # Outside window: soft decay, not reject
        excess = age - window_days
        return round(max(0.0, 8.0 * (0.5 ** (excess / max(half_life, 1.0)))), 2)

    # Exponential decay by intent half-life
    score = 20.0 * (0.5 ** (age / max(half_life, 1.0)))
    return round(max(0.0, min(20.0, score)), 2)
