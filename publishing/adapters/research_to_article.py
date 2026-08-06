"""ResearchBrief → Article adapter."""

from __future__ import annotations

from datetime import datetime

from publishing.adapters.case_to_article import case_to_article
from publishing.adapters.signal_to_article import signal_to_article
from publishing.article import Article, ArticleItem, ArticleMeta, generate_uuid
from research.models import CaseStudy, IndustrySignal, ResearchBrief
from utils.helpers import CST


def research_brief_to_article(
    brief: ResearchBrief,
    *,
    signals: list[IndustrySignal] | None = None,
    cases: list[CaseStudy] | None = None,
    issue: int = 0,
    date: str = "",
    template: str = "deep_insight",
) -> Article:
    """Compose a ResearchBrief into a channel Article without embedding full research graphs."""
    publish_date = date or datetime.now(CST).strftime("%Y-%m-%d")
    signals = signals or []
    cases = cases or []

    if template == "signal_digest" and signals:
        article = signal_to_article(signals[0], issue=issue)
        article.metadata.source = "signal_digest"
        return article
    if template == "case_study" and cases:
        article = case_to_article(cases[0], issue=issue, date=publish_date)
        article.metadata.source = "case_study"
        return article

    items: list[ArticleItem] = []
    for signal in signals[:5]:
        items.append(
            ArticleItem(
                title=signal.title,
                excerpt=signal.summary,
                source_url="",
                source_name="IndustrySignal",
                insight=signal.judgment,
                why_it_matters=signal.why_it_matters,
                level="core",
            )
        )
    for case in cases[:3]:
        items.append(
            ArticleItem(
                title=case.title,
                excerpt=case.problem,
                source_url="",
                source_name="CaseStudy",
                insight=case.solution,
                level="important",
            )
        )
    if not items:
        items.append(
            ArticleItem(
                title=brief.title,
                excerpt=brief.summary,
                source_url="",
                source_name="ResearchBrief",
                level="core",
            )
        )

    return Article(
        metadata=ArticleMeta(
            uuid=generate_uuid(template, publish_date, issue or 1),
            slug=f"{template}-{brief.slug}",
            source=template,
            issue=issue or 1,
            created_at=datetime.now(CST).isoformat(timespec="seconds"),
        ),
        title=brief.title,
        date=publish_date,
        summary=[brief.summary],
        sections=items,
        signal=brief.summary,
    )
