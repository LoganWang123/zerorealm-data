"""Parser — MDX → Article（含版本迁移）.

解析 output_daily/*.mdx 的 YAML frontmatter 为 Article 对象。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from publishing.article import (
    Article,
    ArticleItem,
    ArticleMeta,
    ArticleSection,
    Lifecycle,
    generate_uuid,
)


class ArticleParser:
    """MDX/YAML → Article 解析器."""

    def parse(self, path: str) -> Article:
        """解析 MDX 文件为 Article."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Article file not found: {path}")

        content = p.read_text(encoding="utf-8")
        data = self._extract_frontmatter(content)

        return self._build_article(data, p.stem)

    def _extract_frontmatter(self, content: str) -> dict:
        """提取 YAML frontmatter（--- 包裹）."""
        content = content.strip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return yaml.safe_load(parts[1]) or {}
        # 整体当 YAML 解析
        return yaml.safe_load(content) or {}

    def _build_article(self, data: dict, stem: str) -> Article:
        """从 dict 构建 Article."""
        title = data.get("title", "")
        date = str(data.get("date", ""))
        issue = int(data.get("issue", 1))
        summary = data.get("summary", [])
        source = "daily"  # 默认日报

        # 确定性 UUID
        uuid = generate_uuid(source, date, issue)

        # 解析 sections
        sections = []
        for sec_data in data.get("sections", []):
            items = [
                ArticleItem(
                    title=item.get("title", ""),
                    excerpt=item.get("excerpt", ""),
                    source_url=item.get("source_url", ""),
                    source_name=item.get("source_name", ""),
                )
                for item in sec_data.get("items", [])
            ]
            sections.append(ArticleSection(type=sec_data.get("type", ""), items=items))

        now = datetime.now(timezone.utc).isoformat()

        metadata = ArticleMeta(
            uuid=uuid,
            slug=f"{source}-{date}",
            source=source,
            issue=issue,
            created_at=now,
            updated_at=now,
            schema_version=1,
            content_revision=1,
            lifecycle=Lifecycle.DRAFT,
        )

        return Article(
            metadata=metadata,
            title=title,
            date=date,
            summary=summary,
            sections=sections,
            cover="",  # 使用默认封面
            author="ZeroRealm AI",
            tags=[source],
        )
