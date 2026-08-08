"""Source quality classification for Discovery ranking (not evidence truth)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


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


# Domain suffix → (source_type, tier). Prefer longest/most specific match via endswith.
_DOMAIN_RULES: tuple[tuple[str, SourceType, SourceTier], ...] = (
    # Government / standards
    ("gov.cn", SourceType.GOVERNMENT, SourceTier.S),
    ("gov.uk", SourceType.GOVERNMENT, SourceTier.S),
    ("europa.eu", SourceType.GOVERNMENT, SourceTier.S),
    # Exchanges / disclosure
    ("sse.com.cn", SourceType.EXCHANGE, SourceTier.S),
    ("szse.cn", SourceType.EXCHANGE, SourceTier.S),
    ("cninfo.com.cn", SourceType.EXCHANGE, SourceTier.S),
    ("hkexnews.hk", SourceType.EXCHANGE, SourceTier.S),
    ("sec.gov", SourceType.EXCHANGE, SourceTier.S),
    # Academic
    ("edu.cn", SourceType.ACADEMIC, SourceTier.S),
    ("ac.cn", SourceType.ACADEMIC, SourceTier.S),
    ("arxiv.org", SourceType.ACADEMIC, SourceTier.S),
    ("ieee.org", SourceType.ACADEMIC, SourceTier.S),
    ("nature.com", SourceType.ACADEMIC, SourceTier.S),
    ("sciencedirect.com", SourceType.ACADEMIC, SourceTier.S),
    # Associations / research orgs
    ("ccfa.org.cn", SourceType.ASSOCIATION, SourceTier.A),
    # Major media
    ("xinhuanet.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("people.com.cn", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("reuters.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("bloomberg.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("caixin.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("yicai.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("ft.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("wsj.com", SourceType.MAJOR_MEDIA, SourceTier.A),
    ("36kr.com", SourceType.INDUSTRY_MEDIA, SourceTier.B),
    ("ifanr.com", SourceType.INDUSTRY_MEDIA, SourceTier.B),
    ("leiphone.com", SourceType.INDUSTRY_MEDIA, SourceTier.B),
    ("latepost.com", SourceType.INDUSTRY_MEDIA, SourceTier.B),
    ("huaon.com", SourceType.INDUSTRY_MEDIA, SourceTier.B),
    # Encyclopedia / aggregator (allowed, lower priority)
    ("wikipedia.org", SourceType.ENCYCLOPEDIA, SourceTier.C),
    ("baike.baidu.com", SourceType.ENCYCLOPEDIA, SourceTier.C),
    ("baike.com", SourceType.ENCYCLOPEDIA, SourceTier.C),
    ("zh.wikipedia.org", SourceType.ENCYCLOPEDIA, SourceTier.C),
    ("toutiao.com", SourceType.AGGREGATOR, SourceTier.C),
    ("sohu.com", SourceType.AGGREGATOR, SourceTier.C),
    ("163.com", SourceType.AGGREGATOR, SourceTier.C),
    ("sina.com.cn", SourceType.AGGREGATOR, SourceTier.C),
    ("qq.com", SourceType.AGGREGATOR, SourceTier.C),
)

_OFFICIAL_PATH_HINTS = (
    "/announcement",
    "/notice",
    "/ir/",
    "/investor",
    "/press",
    "/newsroom",
    "/disclosure",
)

_VENDOR_TITLE_HINTS = (
    "产品中心",
    "解决方案",
    "官网",
    "软硬件",
    "采购",
    "报价",
    "product",
    "solution",
)


def canonical_domain(url: str) -> str:
    host = (urlsplit(url or "").netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def classify_source(
    url: str,
    *,
    title: str = "",
    publisher: str = "",
) -> SourceClassification:
    """Classify provenance quality for ranking — never evidence validity."""
    domain = canonical_domain(url)
    path = (urlsplit(url or "").path or "").lower()
    title_l = (title or "").lower()
    pub = (publisher or "").strip() or domain or "unknown"

    for suffix, source_type, tier in _DOMAIN_RULES:
        if domain == suffix or domain.endswith("." + suffix):
            is_official = source_type in {
                SourceType.GOVERNMENT,
                SourceType.EXCHANGE,
                SourceType.OFFICIAL,
            }
            return SourceClassification(
                source_type=source_type,
                source_tier=tier,
                publisher=pub,
                canonical_domain=domain,
                is_official=is_official,
            )

    # Company IR / announcement paths on otherwise unknown domains → official-ish
    if any(hint in path for hint in _OFFICIAL_PATH_HINTS):
        return SourceClassification(
            source_type=SourceType.COMPANY,
            source_tier=SourceTier.S,
            publisher=pub,
            canonical_domain=domain,
            is_official=True,
        )

    # Vendor / marketing heuristics (still Candidate-eligible, lower tier)
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

    # Open docs / company product docs
    if "opendocs." in domain or domain.endswith(".alipay.com") or "/product" in path:
        return SourceClassification(
            source_type=SourceType.COMPANY,
            source_tier=SourceTier.B,
            publisher=pub,
            canonical_domain=domain,
            is_official=False,
        )

    return SourceClassification(
        source_type=SourceType.UNKNOWN,
        source_tier=SourceTier.C,
        publisher=pub,
        canonical_domain=domain,
        is_official=False,
    )


TIER_SCORE: dict[SourceTier, float] = {
    SourceTier.S: 30.0,
    SourceTier.A: 18.0,
    SourceTier.B: 8.0,
    SourceTier.C: 0.0,
}
