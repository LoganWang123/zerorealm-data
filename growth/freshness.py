"""Freshness gates for channel reports vs a review date.

Stale reports must not be copied into current_experiment channel counts.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class FreshnessError(ValueError):
    """Raised when a review date or period cannot be compared."""


def parse_iso_date(value: str, *, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise FreshnessError(f"invalid {field_name}: {value!r}") from exc


def lag_days(period_end: str, review_date: str) -> int:
    end = parse_iso_date(period_end, field_name="period_end")
    review = parse_iso_date(review_date, field_name="review_date")
    return (review - end).days


def classify_freshness(
    *,
    period_end: str,
    review_date: str,
    experiment_start: str,
    current_max_lag_days: int = 1,
) -> dict[str, Any]:
    """Return a privacy-safe freshness record (no raw rows)."""
    lag = lag_days(period_end, review_date)
    end = parse_iso_date(period_end, field_name="period_end")
    start = parse_iso_date(experiment_start, field_name="experiment_start")
    review = parse_iso_date(review_date, field_name="review_date")
    status = "current" if lag <= current_max_lag_days else "stale"
    covers_experiment_start = end >= start
    covers_review_date = end >= review
    can_fill_current_experiment = status == "current" and covers_experiment_start
    return {
        "period_end": period_end,
        "review_date": review_date,
        "experiment_start": experiment_start,
        "lag_days": lag,
        "status": status,
        "covers_experiment_start": covers_experiment_start,
        "covers_review_date": covers_review_date,
        "can_fill_current_experiment": can_fill_current_experiment,
    }
