"""Publication date extraction with provenance (never invent crawl/discover time)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from discovery.freshness import parse_published_at


class DateConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Lower rank number = higher priority for canonical published_at.
_SOURCE_PRIORITY: dict[str, int] = {
    "jsonld.datePublished": 1,
    "meta.article:published_time": 2,
    "meta.og:published_time": 3,
    "meta.pubdate": 4,
    "html.time": 5,
    "body_pattern.published": 6,
    "jsonld.dateModified": 50,
    "meta.article:modified_time": 51,
    "meta.og:updated_time": 52,
    "body_pattern.modified": 53,
}


@dataclass(frozen=True)
class DateCandidate:
    value: str
    source: str
    kind: str  # published | modified
    confidence: DateConfidence

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "source": self.source,
            "kind": self.kind,
            "confidence": self.confidence.value,
        }


@dataclass
class PublicationDateResult:
    published_at: str | None = None
    published_at_source: str = "unknown"
    published_at_confidence: str = DateConfidence.LOW.value
    modified_at: str | None = None
    modified_at_source: str = "unknown"
    date_conflict: bool = False
    date_candidates: list[DateCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "published_at": self.published_at,
            "published_at_source": self.published_at_source,
            "published_at_confidence": self.published_at_confidence,
            "modified_at": self.modified_at,
            "modified_at_source": self.modified_at_source,
            "date_conflict": self.date_conflict,
            "date_candidates": [c.to_dict() for c in self.date_candidates],
            "warnings": list(self.warnings),
        }


_PUBLISH_PATTERNS = [
    re.compile(r"发布时间[:：]\s*([0-9]{4}[-/\.年][0-9]{1,2}[-/\.月][0-9]{1,2}日?(?:\s+[0-9:]{5,8})?)"),
    re.compile(r"发布日期[:：]\s*([0-9]{4}[-/\.年][0-9]{1,2}[-/\.月][0-9]{1,2}日?(?:\s+[0-9:]{5,8})?)"),
    re.compile(r"发布于\s*([0-9]{4}[-/\.年][0-9]{1,2}[-/\.月][0-9]{1,2}日?(?:\s+[0-9:]{5,8})?)"),
    re.compile(
        r"Published(?:\s+on)?[:\s]+([0-9]{4}[-/\.][0-9]{1,2}[-/\.][0-9]{1,2}(?:[T\s][0-9:]{5,8}Z?)?)",
        re.I,
    ),
]

_MODIFIED_PATTERNS = [
    re.compile(r"更新时间[:：]\s*([0-9]{4}[-/\.年][0-9]{1,2}[-/\.月][0-9]{1,2}日?(?:\s+[0-9:]{5,8})?)"),
    re.compile(r"更新于\s*([0-9]{4}[-/\.年][0-9]{1,2}[-/\.月][0-9]{1,2}日?(?:\s+[0-9:]{5,8})?)"),
    re.compile(
        r"(?:Last\s+modified|Updated)(?:\s+on)?[:\s]+([0-9]{4}[-/\.][0-9]{1,2}[-/\.][0-9]{1,2}(?:[T\s][0-9:]{5,8}Z?)?)",
        re.I,
    ),
]


def _normalize_date(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace("年", "-").replace("月", "-").replace("日", "")
    try:
        dt = date_parser.parse(text, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
    # Prefer timezone-aware ISO when available; else naive ISO seconds.
    if dt.tzinfo is not None:
        return dt.isoformat(timespec="seconds")
    return dt.replace(microsecond=0).isoformat()


def _add_candidate(
    rows: list[DateCandidate],
    *,
    raw: str,
    source: str,
    kind: str,
    confidence: DateConfidence,
) -> None:
    value = _normalize_date(raw)
    if not value:
        return
    key = (value, source, kind)
    if any((c.value, c.source, c.kind) == key for c in rows):
        return
    rows.append(DateCandidate(value=value, source=source, kind=kind, confidence=confidence))


def _walk_jsonld(node: Any, rows: list[DateCandidate]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, rows)
        return
    if not isinstance(node, dict):
        return
    if node.get("datePublished"):
        _add_candidate(
            rows,
            raw=str(node["datePublished"]),
            source="jsonld.datePublished",
            kind="published",
            confidence=DateConfidence.HIGH,
        )
    if node.get("dateModified"):
        _add_candidate(
            rows,
            raw=str(node["dateModified"]),
            source="jsonld.dateModified",
            kind="modified",
            confidence=DateConfidence.HIGH,
        )
    graph = node.get("@graph")
    if graph is not None:
        _walk_jsonld(graph, rows)


def extract_publication_dates(
    html: str = "",
    *,
    text: str = "",
) -> PublicationDateResult:
    """Extract published/modified dates from HTML/text with provenance."""
    rows: list[DateCandidate] = []
    soup = BeautifulSoup(html or "", "lxml") if html else BeautifulSoup("", "lxml")

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _walk_jsonld(payload, rows)

    meta_map = {
        "article:published_time": ("meta.article:published_time", "published", DateConfidence.HIGH),
        "og:published_time": ("meta.og:published_time", "published", DateConfidence.HIGH),
        "pubdate": ("meta.pubdate", "published", DateConfidence.MEDIUM),
        "publishdate": ("meta.pubdate", "published", DateConfidence.MEDIUM),
        "article:modified_time": ("meta.article:modified_time", "modified", DateConfidence.HIGH),
        "og:updated_time": ("meta.og:updated_time", "modified", DateConfidence.MEDIUM),
    }
    for meta in soup.find_all("meta"):
        key = (meta.get("property") or meta.get("name") or "").strip().lower()
        content = (meta.get("content") or "").strip()
        if not key or not content:
            continue
        rule = meta_map.get(key)
        if rule:
            source, kind, conf = rule
            _add_candidate(rows, raw=content, source=source, kind=kind, confidence=conf)

    for time_tag in soup.find_all("time"):
        raw = (time_tag.get("datetime") or time_tag.get_text(" ", strip=True) or "").strip()
        if raw:
            _add_candidate(
                rows,
                raw=raw,
                source="html.time",
                kind="published",
                confidence=DateConfidence.MEDIUM,
            )

    body_text = text or soup.get_text("\n", strip=True)
    for pattern in _PUBLISH_PATTERNS:
        match = pattern.search(body_text)
        if match:
            _add_candidate(
                rows,
                raw=match.group(1),
                source="body_pattern.published",
                kind="published",
                confidence=DateConfidence.MEDIUM,
            )
    for pattern in _MODIFIED_PATTERNS:
        match = pattern.search(body_text)
        if match:
            _add_candidate(
                rows,
                raw=match.group(1),
                source="body_pattern.modified",
                kind="modified",
                confidence=DateConfidence.MEDIUM,
            )

    published = [c for c in rows if c.kind == "published"]
    modified = [c for c in rows if c.kind == "modified"]
    published.sort(key=lambda c: (_SOURCE_PRIORITY.get(c.source, 99), c.value))
    modified.sort(key=lambda c: (_SOURCE_PRIORITY.get(c.source, 99), c.value))

    result = PublicationDateResult(date_candidates=list(rows))
    if published:
        best = published[0]
        result.published_at = best.value
        result.published_at_source = best.source
        result.published_at_confidence = best.confidence.value
        distinct = {parse_published_at(c.value).date() for c in published if parse_published_at(c.value)}
        if len(distinct) > 1:
            result.date_conflict = True
            result.warnings.append("PUBLICATION_DATE_CONFLICT")
    if modified:
        best_m = modified[0]
        result.modified_at = best_m.value
        result.modified_at_source = best_m.source

    return result
