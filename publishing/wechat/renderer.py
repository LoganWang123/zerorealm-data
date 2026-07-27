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
        """构建完整 HTML (V4.2: 主题驱动情报产品)."""
        parts: list[str] = []

        # 1. 标题区
        parts.append(templates.title_header(article.title, article.date))

        # 2. 开头引导语
        parts.append(templates.intro_block())

        # 3. 📡 Signal（V4.2: 放到最前面，品牌IP）
        signal_text = getattr(article, "signal", "")
        signal_no = getattr(article, "signal_no", 0)
        if signal_text and isinstance(signal_text, str):
            parts.append(templates.signal_brand_block(signal_no, signal_text))

        # 4. 🚨 CEO Radar（V4.2新增）
        ceo_radar = getattr(article, "ceo_radar", None)
        if ceo_radar:
            parts.append(templates.ceo_radar_block(ceo_radar))

        # 5. 🎯 Decision（V4.3: 角色化决策）
        decision = getattr(article, "decision", None)
        if decision and isinstance(decision, dict):
            parts.append(templates.decision_block(decision))
        else:
            # 兼容旧版 ceo_action
            ceo_action = getattr(article, "ceo_action", None)
            if ceo_action:
                parts.append(templates.ceo_action_block(ceo_action))

        # 6. 📈 Signal展开（趋势）
        if getattr(article, "trend", ""):
            parts.append(templates.trend_block(article.trend))

        # 7. 🌡 行业温度
        industry_temp = getattr(article, "industry_temp", None)
        if industry_temp:
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

        # 8. 📡 证据（sections）
        sections = getattr(article, "sections", [])
        if sections:
            parts.append(templates.section_header("📡 今日证据"))

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

        # 9. 💡 Opportunity + ⚠️ Risk
        opportunity = getattr(article, "opportunity", "")
        risk = getattr(article, "risk", "")
        if opportunity or risk:
            parts.append(templates.opportunity_risk_block(opportunity, risk))

        # 9.5 🌍 海外信号（V5.0新增）
        overseas = getattr(article, "overseas_signal", None)
        if overseas and isinstance(overseas, dict):
            parts.append(templates.overseas_signal_block(
                overseas.get("trend", ""), overseas.get("why_china", "")
            ))

        # 10. 💎 First Principle（V4.4新增）
        fp = getattr(article, "first_principle", None)
        if fp:
            if isinstance(fp, dict):
                parts.append(templates.first_principle_block(
                    fp.get("no", 0), fp.get("content", "")
                ))
            elif hasattr(fp, "no"):
                parts.append(templates.first_principle_block(fp.no, fp.content))

        # 11. 📊 One Chart（V4.2新增）
        one_chart = getattr(article, "one_chart", None)
        if one_chart:
            parts.append(templates.one_chart_block(one_chart))

        # 11. 📊 One Number
        dp = getattr(article, "data_point", None)
        if dp and getattr(dp, "number", ""):
            parts.append(templates.data_point_block(
                dp.number, dp.label, dp.interpretation
            ))

        # 12. 🔮 预测
        prediction = getattr(article, "prediction", None)
        if prediction:
            if isinstance(prediction, dict):
                parts.append(templates.prediction_block(
                    prediction.get("content", ""),
                    prediction.get("confidence", 0),
                    prediction.get("basis", ""),
                    confidence_pct=prediction.get("confidence_pct", 0),
                    drivers=prediction.get("drivers", None),
                    blockers=prediction.get("blockers", None),
                    risk_note=prediction.get("risk_note", ""),
                ))
            else:
                parts.append(templates.prediction_block(
                    getattr(prediction, "content", ""),
                    getattr(prediction, "confidence", 0),
                    getattr(prediction, "basis", ""),
                    confidence_pct=getattr(prediction, "confidence_pct", 0),
                ))

        # 13. 🔄 Counter View
        if getattr(article, "counter_view", ""):
            parts.append(templates.counter_view_block(article.counter_view))

        # 14. 👁 Watchlist（V4.3新增）
        watchlist = getattr(article, "watchlist", None)
        if watchlist:
            parts.append(templates.watchlist_block(watchlist))

        # 15. 💬 互动
        if getattr(article, "discussion", ""):
            parts.append(templates.discussion_block(article.discussion))

        # 15. 📊 ZeroRealm Exclusive
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

        # 16. 📅 明日关注
        if getattr(article, "tomorrow", None):
            parts.append(templates.tomorrow_block(article.tomorrow))

        # 17. 尾部
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
                tags_list = []
                if tags_raw.get("industry"):
                    tags_list.append(tags_raw["industry"])
                tags_list.extend(tags_raw.get("topics", []))
            elif hasattr(tags_raw, "industry"):
                tags_list = [tags_raw.industry] + list(getattr(tags_raw, "topics", []))

        # V4.1: 获取 impact
        impact_raw = getattr(item, "impact", None)
        impact_dict = None
        if impact_raw:
            if isinstance(impact_raw, dict):
                impact_dict = impact_raw
            elif hasattr(impact_raw, "operators"):
                impact_dict = {
                    "operators": impact_raw.operators,
                    "device_makers": impact_raw.device_makers,
                    "brands": impact_raw.brands,
                    "investors": impact_raw.investors,
                }

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
            impact=impact_dict,
            level=getattr(item, "level", ""),
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
