"""WechatRenderer — 微信公众号渲染器.

Article + RenderContext → RenderResult（内联 CSS HTML）。
内部持有 MediaStorage（DI），不通过 Context 传递。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from publishing.base import BaseRenderer
from publishing.models import MediaReference, RenderResult, WechatMetadata
from publishing.wechat import templates

if TYPE_CHECKING:
    from publishing.article import Article
    from publishing.base import BaseMediaStorage
    from publishing.models import RenderContext


def strip_html(html: str) -> str:
    """去除 HTML 标签，返回纯文本."""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def count_words(text: str) -> int:
    """统计词数（中文按字符，英文按空格分词）."""
    # 简单策略：中文字符数 + 英文单词数
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return chinese_chars + english_words


class WechatRenderer(BaseRenderer):
    """微信公众号渲染器."""

    def __init__(self, media_storage: BaseMediaStorage):
        self._storage = media_storage

    def render(self, article: Article, context: RenderContext) -> RenderResult:
        """渲染文章为微信 HTML."""
        html = self._build_html(article, context)
        media = self._process_media(html)
        html = self._sanitize(html)

        plain_text = strip_html(html)

        return RenderResult(
            article_uuid=article.metadata.uuid,
            title=article.title,
            body=html,
            summary=article.summary[0] if article.summary else "",
            cover=context.asset_manager.get_cover(article),
            author=context.config.wechat.author,
            word_count=count_words(plain_text),
            char_count=len(plain_text),
            media=media,
            channel_metadata=WechatMetadata(
                copyright=context.config.wechat.copyright,
                digest=article.summary[0] if article.summary else "",
                need_open_comment=0,
            ),
        )

    def _build_html(self, article: Article, context: RenderContext) -> str:
        """构建完整 HTML."""
        parts: list[str] = []

        # 标题区
        parts.append(templates.title_header(article.title, article.date))

        # 摘要要点
        if article.summary:
            parts.append(templates.summary_block(article.summary))

        # 各板块
        for section in article.sections:
            section_title = templates.SECTION_TITLES.get(section.type, section.type)
            parts.append(templates.section_header(section_title))

            for idx, item in enumerate(section.items, 1):
                parts.append(
                    templates.news_item(
                        title=item.title,
                        excerpt=item.excerpt,
                        source_name=item.source_name,
                        index=idx,
                    )
                )

        # 尾部
        parts.append(templates.footer(article.author))

        # 包裹容器
        body = "\n".join(parts)
        return (
            f'<div style="max-width:100%;padding:16px;'
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;'
            f'font-size:16px;line-height:1.75;color:#333;">'
            f"{body}</div>"
        )

    def _process_media(self, html: str) -> list[MediaReference]:
        """处理正文中的媒体（当前日报无正文图片，预留）."""
        # 未来：解析 <img> 标签，上传到微信 CDN，替换 URL
        return []

    def _sanitize(self, html: str) -> str:
        """内部清洗：移除微信不支持的标签/属性."""
        # 移除 script / iframe
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL)
        # 移除 class / id 属性（微信不需要）
        html = re.sub(r'\s+(class|id)="[^"]*"', "", html)
        return html
