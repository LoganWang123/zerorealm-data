"""ArticleValidator — Article 完整性校验."""

from __future__ import annotations

from publishing.article import Article
from publishing.models import ValidationResult


class ArticleValidator:
    """校验 Article 完整性（含 warnings）."""

    def validate(self, article: Article) -> ValidationResult:
        """校验文章，返回 ValidationResult."""
        errors: list[str] = []
        warnings: list[str] = []

        # 必填字段
        if not article.title:
            errors.append("title is empty")
        if not article.date:
            errors.append("date is empty")
        if not article.metadata.uuid:
            errors.append("metadata.uuid is empty")
        if not article.sections:
            errors.append("no sections found")

        # summary 检查
        if not article.summary:
            warnings.append("summary is empty, digest will fallback")

        # sections 内容检查
        total_items = 0
        for section in article.sections:
            if not section.type:
                errors.append(f"section type is empty")
            if not section.items:
                warnings.append(f"section '{section.type}' has no items")
            for item in section.items:
                total_items += 1
                if not item.title:
                    errors.append(f"item title is empty in section '{section.type}'")

        if total_items == 0 and not errors:
            warnings.append("article has 0 news items")

        # cover 检查
        if not article.cover:
            warnings.append("cover not set, will use default")

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
