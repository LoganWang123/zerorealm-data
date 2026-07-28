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


def today_path(date: str | None = None) -> str:
    """Return a YYYY/MM/DD path for an explicit date or today in China time."""
    if date:
        return datetime.strptime(date, "%Y-%m-%d").strftime("%Y/%m/%d")
    return datetime.now(CST).strftime("%Y/%m/%d")
