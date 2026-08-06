"""CaseStudy → Article adapter."""

from __future__ import annotations

from datetime import datetime

from publishing.article import Article, ArticleItem, ArticleMeta, generate_uuid
from research.models import CaseStudy
from utils.helpers import CST


def case_to_article(case: CaseStudy, *, issue: int = 0, date: str = "") -> Article:
    """Map one case study into the publish exchange model."""
    publish_date = date or datetime.now(CST).strftime("%Y-%m-%d")
    results = "；".join(case.public_results) if case.public_results else "暂无公开量化结果"
    limitations = "；".join(case.limitations) if case.limitations else "需结合场景判断"
    return Article(
        metadata=ArticleMeta(
            uuid=generate_uuid("case", publish_date, issue or 1),
            slug=f"case-{case.slug}",
            source="case_study",
            issue=issue or 1,
            created_at=datetime.now(CST).isoformat(timespec="seconds"),
        ),
        title=f"案例拆解｜{case.title}",
        date=publish_date,
        summary=[case.problem, case.solution, results],
        counter_view=f"局限与反方：{limitations}",
        sections=[
            ArticleItem(
                title="问题",
                excerpt=case.problem,
                source_url="",
                source_name="ZeroRealm Case",
                level="core",
            ),
            ArticleItem(
                title="方案",
                excerpt=case.solution,
                source_url="",
                source_name="ZeroRealm Case",
                insight=case.how_it_works,
                level="core",
            ),
            ArticleItem(
                title="公开结果",
                excerpt=results,
                source_url="",
                source_name="ZeroRealm Case",
                level="important",
            ),
        ],
    )
