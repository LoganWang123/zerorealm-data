"""Common helper utilities."""

import hashlib
from datetime import datetime, timezone, timedelta


CST = timezone(timedelta(hours=8))  # China Standard Time


def generate_id(source: str, url: str) -> str:
    """Generate deterministic ID from source + url (first 16 chars of SHA256)."""
    return hashlib.sha256(f"{source}{url}".encode()).hexdigest()[:16]


def now_iso() -> str:
    """Current time in ISO 8601 with CST timezone."""
    return datetime.now(CST).isoformat(timespec="seconds")


def generate_run_id() -> str:
    """Generate run_id in format YYYYMMDD_HHMMSS."""
    return datetime.now(CST).strftime("%Y%m%d_%H%M%S")


def today_path() -> str:
    """Return today's date path segment: YYYY/MM/DD."""
    return datetime.now(CST).strftime("%Y/%m/%d")
