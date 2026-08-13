"""Zero/missing-denominator-safe rate helpers for growth funnels."""

from __future__ import annotations


def safe_rate(
    numerator: int | float | None, denominator: int | float | None
) -> float | None:
    """Return numerator/denominator, or None when denominator is zero or missing.

    Callers must treat None as \"rate unavailable\" (n/a), never as 0.0.
    """
    if denominator is None or denominator == 0:
        return None
    if numerator is None:
        return None
    return float(numerator) / float(denominator)


def format_rate(rate: float | None, *, digits: int = 4) -> str:
    """Human-readable rate; None becomes an explicit unavailable marker."""
    if rate is None:
        return "n/a (zero/missing denominator)"
    return f"{rate:.{digits}f}"
