"""WechatRenderer — 微信公众号渲染器 V6.

Article + RenderContext → RenderResult（内联 CSS HTML）。
V6: 新零售行业情报官模式
- 三屏首页结构：Signal → Radar+Decision → 深度分析
- 内容分层：2篇深度（Why Now）+ 快讯列表
- 新增 Today's Number / Industry Map / ZeroRealm Lens / Prediction Score
- Watchlist 看板化（状态灯）
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
    """微信公众号渲染器 V6."""

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
        """构建完整 HTML (V7: 6栏目固定阅读节奏)."""
        parts: list[str] = []

        # === ① Signal ===
        parts.append(templates.title_header(article.title, article.date))
        parts.append(templates.intro_block())

        signal_text = getattr(article, "signal", "")
        signal_no = getattr(article, "signal_no", 0)
        if signal_text and isinstance(signal_text, str):
            parts.append(templates.signal_brand_block(signal_no, signal_text))

        # === ② CEO Radar（统一模块：focus + prediction_check + tomorrow） ===
        ceo_radar = getattr(article, "ceo_radar", None)
        if ceo_radar:
            parts.append(self._render_ceo_radar(ceo_radar, article))

        # === ③ 今日必须看（2篇深度） ===
        sections = getattr(article, "sections", [])
        core_items = []
        quick_items = []
        if sections:
            for item in sections:
                level = getattr(item, "level", "") if hasattr(item, "level") else (
                    item.get("level", "") if isinstance(item, dict) else ""
                )
                if level == "core":
                    core_items.append(item)
                elif level == "quick":
                    quick_items.append(item)
                else:
                    core_items.append(item)

        if core_items:
            parts.append(templates.section_header("⭐ 今日必须看"))
            for idx, item in enumerate(core_items[:2], 1):
                parts.append(self._render_news_item(item, idx))

        # === ④ 快讯（3~5条，每条+一句判断） ===
        if quick_items:
            parts.append(templates.section_header("⚡ 快讯"))
            parts.append(templates.quick_news_list(
                [self._item_to_dict(q) for q in quick_items]
            ))

        # === ⑤ Signal Matrix / Trend ===
        # V9: 优先使用 trend（带 direction+streak），否则回退 signal_matrix
        trend = getattr(article, "trend", None)
        if trend and isinstance(trend, list) and trend and isinstance(trend[0], dict) and "direction" in trend[0]:
            parts.append(templates.trend_v9_block(trend))
        else:
            signal_matrix = getattr(article, "signal_matrix", None)
            if signal_matrix and isinstance(signal_matrix, list):
                parts.append(templates.signal_matrix_block(signal_matrix))

        # === ⑥ Decision（Action Card） ===
        decision = getattr(article, "decision", None)
        if decision and isinstance(decision, dict):
            parts.append(templates.decision_block(decision))

        # === ⑦ Alpha（独家数据） ===
        alpha = getattr(article, "alpha", None)
        if alpha and isinstance(alpha, dict):
            parts.append(templates.alpha_block(alpha))

        # === ⑧ 数据角 ===
        parts.append(self._render_data_corner(article))

        # === 尾部 ===
        parts.append(templates.footer(article.author))

        # 包裹容器
        body = "\n".join(parts)
        return (
            f'<div style="max-width:100%;padding:16px;'
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;'
            f'font-size:16px;line-height:1.75;color:#333;">'
            f"{body}</div>"
        )

    def _render_ceo_radar(self, ceo_radar, article) -> str:
        """渲染 CEO Radar（V9: 持续追踪 + prediction_validation）."""
        # V9 新格式：dict with tracking / prediction_validation
        if isinstance(ceo_radar, dict):
            tracking = ceo_radar.get("tracking", [])
            prediction_check = ceo_radar.get("prediction_validation", [])
            focus = ceo_radar.get("focus", [])
            tomorrow = ceo_radar.get("tomorrow", [])
        else:
            # 兼容旧格式（纯列表）
            tracking = []
            focus = ceo_radar if isinstance(ceo_radar, list) else []
            prediction_check = []
            tomorrow = []

        # 合并旧版独立字段
        if not prediction_check:
            ps = getattr(article, "prediction_score", None)
            if ps and isinstance(ps, dict):
                prediction_check = ps.get("history", [])
        if not tomorrow:
            tm = getattr(article, "tomorrow", None)
            if tm and isinstance(tm, list):
                tomorrow = tm

        return templates.ceo_radar_unified_block(
            focus, prediction_check, tomorrow, tracking=tracking
        )

    def _render_data_corner(self, article) -> str:
        """渲染数据角（V7: 合并 Today's Number + 监测数据）."""
        # V7 新格式：data_corner
        data_corner = getattr(article, "data_corner", None)
        if data_corner and isinstance(data_corner, dict):
            return templates.data_corner_block(data_corner)

        # 兼容旧版：从 exclusive_data + todays_number 组装
        exclusive_data = getattr(article, "exclusive_data", None)
        todays_number = getattr(article, "todays_number", None)
        if exclusive_data or todays_number:
            dc = {}
            if todays_number and isinstance(todays_number, dict):
                dc["todays_number"] = todays_number
            if exclusive_data:
                if isinstance(exclusive_data, dict):
                    dc.update(exclusive_data)
                else:
                    dc["sources_monitored"] = getattr(exclusive_data, "sources_monitored", 0)
                    dc["total_items"] = getattr(exclusive_data, "total_items", 0)
                    dc["industry_events"] = getattr(exclusive_data, "industry_events", 0)
                    dc["hot_keywords"] = getattr(exclusive_data, "hot_keywords", [])
            return templates.data_corner_block(dc)
        return ""

    def _render_news_item(self, item, idx: int) -> str:
        """渲染单条新闻（V6: 支持 why_now + spread_line）."""
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

        # 获取 impact
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

        # V6: 获取 why_now 和 spread_line
        why_now_raw = getattr(item, "why_now", None)
        why_now_list = None
        if why_now_raw:
            if isinstance(why_now_raw, list):
                why_now_list = why_now_raw
            elif hasattr(why_now_raw, "__iter__"):
                why_now_list = list(why_now_raw)

        spread_line = getattr(item, "spread_line", "")

        # V9: 获取内嵌 prediction
        prediction_raw = getattr(item, "prediction", None)
        prediction_dict = None
        if prediction_raw:
            if isinstance(prediction_raw, dict):
                prediction_dict = prediction_raw
            elif hasattr(prediction_raw, "content"):
                prediction_dict = {
                    "content": prediction_raw.content,
                    "confidence_pct": getattr(prediction_raw, "confidence_pct", 0),
                    "evidence": getattr(prediction_raw, "evidence", []),
                    "watch": getattr(prediction_raw, "watch", ""),
                }

        # V9: 获取 score
        score_raw = getattr(item, "score", None)
        score_dict = None
        if score_raw:
            if isinstance(score_raw, dict):
                score_dict = score_raw
            elif hasattr(score_raw, "strategic"):
                score_dict = {
                    "strategic": getattr(score_raw, "strategic", 0),
                    "commercial": getattr(score_raw, "commercial", 0),
                    "landing": getattr(score_raw, "landing", 0),
                    "credibility": getattr(score_raw, "credibility", 0),
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
            why_now=why_now_list,
            spread_line=spread_line,
            prediction=prediction_dict,
            score=score_dict,
        )

    def _item_to_dict(self, item) -> dict:
        """将 item 对象转为 dict（用于 quick_news_list）."""
        if isinstance(item, dict):
            return item
        return {
            "title": getattr(item, "title", ""),
            "excerpt": getattr(item, "excerpt", ""),
            "verdict": getattr(item, "verdict", ""),
            "source_name": getattr(item, "source_name", ""),
            "source_url": getattr(item, "source_url", ""),
        }

    def _process_media(self, html: str) -> list[MediaReference]:
        """处理正文中的媒体（当前日报无正文图片，预留）."""
        return []

    def _sanitize(self, html: str) -> str:
        """内部清洗：移除微信不支持的标签/属性."""
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL)
        html = re.sub(r'\s+(class|id)="[^"]*"', "", html)
        return html
