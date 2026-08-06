"""IndustrySignal → Article adapter."""

from __future__ import annotations

from datetime import datetime

from publishing.article import Article, ArticleItem, ArticleMeta, generate_uuid
from research.models import IndustrySignal
from utils.helpers import CST


def signal_to_article(signal: IndustrySignal, *, issue: int = 0) -> Article:
    """Map one industry signal into the publish exchange model."""
    date = signal.published_at[:10] if signal.published_at else datetime.now(CST).strftime(
        "%Y-%m-%d"
    )
    return Article(
        metadata=ArticleMeta(
            uuid=generate_uuid("signal", date, issue or 1),
            slug=f"signal-{signal.slug}",
            source="signal_digest",
            issue=issue or 1,
            created_at=datetime.now(CST).isoformat(timespec="seconds"),
        ),
        title=f"零域信号｜{signal.title}",
        date=date,
        summary=[signal.summary, signal.why_it_matters, signal.judgment],
        signal=signal.judgment,
        sections=[
            ArticleItem(
                title=signal.title,
                excerpt=signal.summary,
                source_url="",
                source_name="ZeroRealm Research",
                insight=signal.judgment,
                why_it_matters=signal.why_it_matters,
                level="core",
            )
        ],
        tags=list(signal.tags),
    )
