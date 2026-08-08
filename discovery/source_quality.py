"""Source quality classification for Discovery ranking (not evidence truth)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from bs4 import BeautifulSoup

DEFAULT_REGISTRY_PATH = Path("config/source_quality.yaml")


class SourceType(str, Enum):
    OFFICIAL = "official"
    GOVERNMENT = "government"
    EXCHANGE = "exchange"
    COMPANY = "company"
    ACADEMIC = "academic"
    ASSOCIATION = "association"
    MAJOR_MEDIA = "major_media"
    INDUSTRY_MEDIA = "industry_media"
    VENDOR = "vendor"
    ENCYCLOPEDIA = "encyclopedia"
    AGGREGATOR = "aggregator"
    UNKNOWN = "unknown"


class SourceTier(str, Enum):
    """Research priority / provenance quality — not fact truth."""

    S = "S"
    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True)
class SourceClassification:
    source_type: SourceType
    source_tier: SourceTier
    publisher: str
    canonical_domain: str
    is_official: bool

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type.value,
            "source_tier": self.source_tier.value,
            "publisher": self.publisher,
            "canonical_domain": self.canonical_domain,
            "is_official": self.is_official,
        }


TIER_SCORE: dict[SourceTier, float] = {
    SourceTier.S: 30.0,
    SourceTier.A: 18.0,
    SourceTier.B: 8.0,
    SourceTier.C: 0.0,
}

_OFFICIAL_PATH_HINTS = (
    "/announcement",
    "/notice",
    "/ir/",
    "/investor",
    "/press",
    "/newsroom",
    "/disclosure",
)

_VENDOR_TITLE_HINTS = ("产品中心", "解决方案", "官网", "软硬件", "采购", "报价", "product", "solution")


def canonical_domain(url: str) -> str:
    host = (urlsplit(url or "").netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


@lru_cache(maxsize=4)
def load_source_quality_registry(path: str | None = None) -> dict[str, dict[str, Any]]:
    target = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not target.is_file():
        return {}
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    domains = data.get("domains") if isinstance(data, dict) else {}
    if not isinstance(domains, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in domains.items():
        if not isinstance(value, dict):
            continue
        normalized[str(key).lower()] = value
    return normalized


def clear_source_quality_cache() -> None:
    load_source_quality_registry.cache_clear()


def _lookup_registry(domain: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if domain in registry:
        return registry[domain]
    # Prefer longest matching suffix (e.g. iot.foxconn.com → foxconn.com)
    matches = [key for key in registry if domain == key or domain.endswith("." + key)]
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return registry[matches[0]]


def extract_publisher_from_html(html: str = "") -> str:
    if not html:
        return ""
    import json

    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            publisher = node.get("publisher")
            if isinstance(publisher, dict):
                name = str(publisher.get("name") or "").strip()
                if name:
                    return name
            elif isinstance(publisher, str) and publisher.strip():
                return publisher.strip()
            graph = node.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and isinstance(item.get("publisher"), dict):
                        name = str(item["publisher"].get("name") or "").strip()
                        if name:
                            return name
    for prop in ("og:site_name", "application-name", "publisher"):
        meta = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if meta and (meta.get("content") or "").strip():
            return str(meta.get("content")).strip()
    return ""


def classify_source(
    url: str,
    *,
    title: str = "",
    publisher: str = "",
    html: str = "",
    registry_path: str | None = None,
) -> SourceClassification:
    """Classify provenance quality for ranking — never evidence validity."""
    domain = canonical_domain(url)
    path = (urlsplit(url or "").path or "").lower()
    title_l = (title or "").lower()
    registry = load_source_quality_registry(registry_path)
    html_publisher = extract_publisher_from_html(html)
    reg = _lookup_registry(domain, registry)

    if reg:
        source_type = SourceType(str(reg.get("source_type") or "unknown"))
        source_tier = SourceTier(str(reg.get("source_tier") or "C"))
        pub = (
            str(publisher or "").strip()
            or str(reg.get("publisher") or "").strip()
            or html_publisher
            or domain
            or "unknown"
        )
        return SourceClassification(
            source_type=source_type,
            source_tier=source_tier,
            publisher=pub,
            canonical_domain=domain,
            is_official=bool(reg.get("official")),
        )

    pub = str(publisher or "").strip() or html_publisher or domain or "unknown"

    if any(hint in path for hint in _OFFICIAL_PATH_HINTS):
        return SourceClassification(
            source_type=SourceType.COMPANY,
            source_tier=SourceTier.S,
            publisher=pub,
            canonical_domain=domain,
            is_official=True,
        )

    if any(hint in title_l for hint in _VENDOR_TITLE_HINTS) or any(
        hint in (title or "") for hint in ("官网", "产品中心", "解决方案")
    ):
        return SourceClassification(
            source_type=SourceType.VENDOR,
            source_tier=SourceTier.C,
            publisher=pub,
            canonical_domain=domain,
            is_official=False,
        )

    if domain.endswith(".edu.cn") or domain.endswith(".ac.cn"):
        return SourceClassification(
            source_type=SourceType.ACADEMIC,
            source_tier=SourceTier.S,
            publisher=pub,
            canonical_domain=domain,
            is_official=False,
        )

    if domain.endswith(".gov.cn"):
        return SourceClassification(
            source_type=SourceType.GOVERNMENT,
            source_tier=SourceTier.S,
            publisher=pub,
            canonical_domain=domain,
            is_official=True,
        )

    return SourceClassification(
        source_type=SourceType.UNKNOWN,
        source_tier=SourceTier.C,
        publisher=pub,
        canonical_domain=domain,
        is_official=False,
    )
