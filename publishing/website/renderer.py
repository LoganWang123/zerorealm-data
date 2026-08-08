"""Website Daily Renderer — Article → website MDX RenderResult."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from publishing.base import BaseRenderer
from publishing.models import MediaReference, RenderResult, WebsiteMetadata
from publishing.website.mdx_adapter import (
    build_website_daily_mdx,
    extract_frontmatter,
    load_source_daily_mdx,
)

if TYPE_CHECKING:
    from publishing.article import Article
    from publishing.models import RenderContext


class WebsiteRenderer(BaseRenderer):
    """Render Daily Article into website content/daily MDX."""

    def __init__(self, source_root: Path | None = None):
        self._source_root = source_root or Path.cwd()

    def render(self, article: Article, context: RenderContext) -> RenderResult:
        del context  # Website Daily reuses source MDX; no HTML theme.
        source_path = load_source_daily_mdx(article.date, self._source_root)
        source_text = source_path.read_text(encoding="utf-8")
        source_data, _ = extract_frontmatter(source_text)
        gate_status = (
            os.getenv("ZEROREALM_DAILY_GATE_STATUS", "").strip()
            or source_data.get("gate_status")
        )
        gate_version = (
            os.getenv("ZEROREALM_DAILY_GATE_VERSION", "").strip()
            or source_data.get("gate_version")
        )
        reviewed_at = (
            os.getenv("ZEROREALM_DAILY_REVIEWED_AT", "").strip()
            or source_data.get("reviewed_at")
        )
        body = build_website_daily_mdx(
            source_text,
            date=article.date,
            title=article.title,
            gate_status=str(gate_status) if gate_status else None,
            gate_version=str(gate_version) if gate_version else None,
            reviewed_at=str(reviewed_at) if reviewed_at else None,
        )
        summary = ""
        if article.summary:
            summary = (
                article.summary[0]
                if isinstance(article.summary, list)
                else str(article.summary)
            )
        elif isinstance(article.signal, str):
            summary = article.signal

        return RenderResult(
            article_uuid=article.metadata.uuid,
            title=article.title,
            body=body,
            summary=summary,
            cover=MediaReference(local_path=article.cover or ""),
            author=article.author or "ZeroRealm AI",
            char_count=len(body),
            channel_metadata=WebsiteMetadata(
                canonical=f"/daily/{article.date}",
                slug=article.date,
                toc=False,
            ),
        )
