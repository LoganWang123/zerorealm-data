"""WechatRenderer — 微信公众号渲染器 V4.

Article + RenderContext → RenderResult（内联 CSS HTML）。
V4: 行业决策解释器模式
- 新增 CEO Action / 行业温度 / 独家数据 / 预测 / Signal品牌
- sections 改为统一列表渲染
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
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return chinese_chars + english_words


class WechatRenderer(BaseRenderer):
    """微信公众号渲染器 V4."""

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
        """构建完整 HTML (V4: 行业决策解释器)."""
        parts: list[str] = []

        # 1. 标题区
        parts.append(templates.title_header(article.title, article.date))

        # 2. 开头引导语
        parts.append(templates.intro_block())

        # 3. ✅ CEO今日行动（V4新增，放最前面）
        ceo_action = getattr(article, "ceo_action", None)
        if ceo_action:
            parts.append(templates.ceo_action_block(ceo_action))

        # 4. 📈 今日趋势
        if getattr(article, "trend", ""):
            parts.append(templates.trend_block(article.trend))

        # 5. 🌡 行业温度（V4新增，替代旧版星级）
        industry_temp = getattr(article, "industry_temp", None)
        if industry_temp:
            # 支持 dict 或对象
            if isinstance(industry_temp, dict):
                temps = industry_temp
            else:
                temps = {
                    "ai_retail": getattr(industry_temp, "ai_retail", 0),
                    "instant_retail": getattr(industry_temp, "instant_retail", 0),
                    "smart_cabinet": getattr(industry_temp, "smart_cabinet", 0),
                    "funding": getattr(industry_temp, "funding", 0),
                    "policy": getattr(industry_temp, "policy", 0),
                }
            parts.append(templates.industry_temp_block(temps))

        # 6. 📌 今日三分钟
        if article.summary:
            parts.append(templates.summary_block(article.summary))

        # 7. 精选深度分析（V4：统一列表，不再分板块）
        sections = getattr(article, "sections", [])
        if sections:
            parts.append(templates.section_header("📡 今日深度"))

            # V4: sections 可能是统一列表（新格式）或分板块列表（旧格式兼容）
            if sections and hasattr(sections[0], "type"):
                # 旧格式：分板块
                for section in sections:
                    for idx, item in enumerate(section.items, 1):
                        parts.append(self._render_news_item(item, idx))
            else:
                # 新格式：统一列表
                for idx, item in enumerate(sections, 1):
                    parts.append(self._render_news_item(item, idx))

        # 8. 📊 ZeroRealm Exclusive（V4新增）
        exclusive_data = getattr(article, "exclusive_data", None)
        if exclusive_data:
            if isinstance(exclusive_data, dict):
                data = exclusive_data
            else:
                data = {
                    "sources_monitored": getattr(exclusive_data, "sources_monitored", 0),
                    "total_items": getattr(exclusive_data, "total_items", 0),
                    "industry_events": getattr(exclusive_data, "industry_events", 0),
                    "funding_events": getattr(exclusive_data, "funding_events", 0),
                    "partnership_events": getattr(exclusive_data, "partnership_events", 0),
                    "new_products": getattr(exclusive_data, "new_products", 0),
                    "hot_keywords": getattr(exclusive_data, "hot_keywords", []),
                    "one_line": getattr(exclusive_data, "one_line", ""),
                }
            parts.append(templates.exclusive_data_block(data))

        # 9. 📊 今日数据
        dp = getattr(article, "data_point", None)
        if dp and getattr(dp, "number", ""):
            parts.append(templates.data_point_block(
                dp.number, dp.label, dp.interpretation
            ))

        # 10. 🔮 未来30天预测（V4新增）
        prediction = getattr(article, "prediction", None)
        if prediction:
            if isinstance(prediction, dict):
                parts.append(templates.prediction_block(
                    prediction.get("content", ""),
                    prediction.get("confidence", 3),
                    prediction.get("basis", ""),
                ))
            else:
                parts.append(templates.prediction_block(
                    getattr(prediction, "content", ""),
                    getattr(prediction, "confidence", 3),
                    getattr(prediction, "basis", ""),
                ))

        # 11. 🔄 不同视角
        if getattr(article, "counter_view", ""):
            parts.append(templates.counter_view_block(article.counter_view))

        # 12. 📡 ZeroRealm Signal（V4品牌IP）
        signal_text = getattr(article, "signal", "")
        signal_no = getattr(article, "signal_no", 0)
        if signal_text:
            # V4: signal 是字符串（一句话），不再是对象
            if isinstance(signal_text, str):
                parts.append(templates.signal_brand_block(signal_no, signal_text))
            else:
                # 旧格式兼容
                pass

        # 13. 💬 今日互动（V4：选择题格式）
        if getattr(article, "discussion", ""):
            parts.append(templates.discussion_block(article.discussion))

        # 14. 📅 明日关注
        if getattr(article, "tomorrow", None):
            parts.append(templates.tomorrow_block(article.tomorrow))

        # 15. 尾部
        parts.append(templates.footer(article.author))

        # 包裹容器
        body = "\n".join(parts)
        return (
            f'<div style="max-width:100%;padding:16px;'
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;'
            f'font-size:16px;line-height:1.75;color:#333;">'
            f"{body}</div>"
        )

    def _render_news_item(self, item, idx: int) -> str:
        """渲染单条新闻（兼容新旧格式）."""
        # 获取 tags（可能是对象或列表）
        tags_raw = getattr(item, "tags", None)
        tags_list = None
        if tags_raw:
            if isinstance(tags_raw, list):
                tags_list = tags_raw
            elif isinstance(tags_raw, dict):
                # 新格式：{industry: "xx", topics: ["a", "b"]}
                tags_list = []
                if tags_raw.get("industry"):
                    tags_list.append(tags_raw["industry"])
                tags_list.extend(tags_raw.get("topics", []))
            elif hasattr(tags_raw, "industry"):
                tags_list = [tags_raw.industry] + list(getattr(tags_raw, "topics", []))

        return templates.news_item(
            title=getattr(item, "title", ""),
            excerpt=getattr(item, "excerpt", ""),
            source_name=getattr(item, "source_name", ""),
            index=idx,
            source_url=getattr(item, "source_url", ""),
            insight=getattr(item, "insight", ""),
            importance=getattr(item, "importance", ""),
            tags=tags_list,
            angle=getattr(item, "angle", ""),
        )

    def _process_media(self, html: str) -> list[MediaReference]:
        """处理正文中的媒体（当前日报无正文图片，预留）."""
        return []

    def _sanitize(self, html: str) -> str:
        """内部清洗：移除微信不支持的标签/属性."""
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL)
        html = re.sub(r'\s+(class|id)="[^"]*"', "", html)
        return html
