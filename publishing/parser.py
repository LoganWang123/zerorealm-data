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
    DataPoint,
    HeatIndex,
    IndustryTemp,
    Prediction,
    Signal,
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
        """从 dict 构建 Article (v4: 行业决策解释器)."""
        title = data.get("title", "")
        date = str(data.get("date", ""))
        issue = int(data.get("issue", 1))
        summary = data.get("summary", [])
        source = "daily"  # 默认日报

        # 确定性 UUID
        uuid = generate_uuid(source, date, issue)

        # 解析 sections
        # V4: 统一列表格式（无 type/items 嵌套）
        # V3: 分板块格式（有 type + items）
        sections = []
        raw_sections = data.get("sections", [])
        if raw_sections:
            first = raw_sections[0]
            if isinstance(first, dict) and "type" in first and "items" in first:
                # V3 格式：分板块
                for sec_data in raw_sections:
                    items = [
                        ArticleItem(
                            title=item.get("title", ""),
                            excerpt=item.get("excerpt", ""),
                            source_url=item.get("source_url", ""),
                            source_name=item.get("source_name", ""),
                            insight=item.get("insight", ""),
                            importance=item.get("importance", ""),
                            confidence=item.get("confidence", ""),
                            action=item.get("action", ""),
                            tags=item.get("tags", []),
                            angle=item.get("angle", ""),
                        )
                        for item in sec_data.get("items", [])
                    ]
                    sections.append(ArticleSection(type=sec_data.get("type", ""), items=items))
            else:
                # V4 格式：统一列表
                sections = [
                    ArticleItem(
                        title=item.get("title", ""),
                        excerpt=item.get("excerpt", ""),
                        source_url=item.get("source_url", ""),
                        source_name=item.get("source_name", ""),
                        insight=item.get("insight", ""),
                        importance=item.get("importance", ""),
                        confidence=item.get("confidence", ""),
                        action=item.get("action", ""),
                        tags=item.get("tags", []),
                        angle=item.get("angle", ""),
                        level=item.get("level", ""),
                        impact=item.get("impact", {}),
                        why_it_matters=item.get("why_it_matters", ""),
                    )
                    for item in raw_sections
                ]

        # data_point
        dp_data = data.get("data_point", {})
        data_point = DataPoint(
            number=dp_data.get("number", "") if dp_data else "",
            label=dp_data.get("label", "") if dp_data else "",
            interpretation=dp_data.get("interpretation", "") if dp_data else "",
        )

        # v3: heat_index (backward compat)
        hi_data = data.get("heat_index", {})
        heat_index = HeatIndex(
            ai_retail=int(hi_data.get("ai_retail", 3)) if hi_data else 3,
            instant_retail=int(hi_data.get("instant_retail", 3)) if hi_data else 3,
            smart_cabinet=int(hi_data.get("smart_cabinet", 3)) if hi_data else 3,
            funding=int(hi_data.get("funding", 2)) if hi_data else 2,
        )

        # v4: industry_temp
        it_data = data.get("industry_temp", {})
        industry_temp = IndustryTemp(
            ai_retail=int(it_data.get("ai_retail", 50)) if it_data else 50,
            instant_retail=int(it_data.get("instant_retail", 50)) if it_data else 50,
            smart_cabinet=int(it_data.get("smart_cabinet", 50)) if it_data else 50,
            funding=int(it_data.get("funding", 30)) if it_data else 30,
            policy=int(it_data.get("policy", 30)) if it_data else 30,
        )

        # v4: prediction
        pred_data = data.get("prediction", {})
        prediction = Prediction(
            content=pred_data.get("content", "") if pred_data else "",
            confidence=int(pred_data.get("confidence", 3)) if pred_data else 3,
            basis=pred_data.get("basis", "") if pred_data else "",
            confidence_pct=int(pred_data.get("confidence_pct", 0)) if pred_data else 0,
        )

        now = datetime.now(timezone.utc).isoformat()

        metadata = ArticleMeta(
            uuid=uuid,
            slug=f"{source}-{date}",
            source=source,
            issue=issue,
            created_at=now,
            updated_at=now,
            schema_version=4,
            content_revision=1,
            lifecycle=Lifecycle.DRAFT,
        )

        # signal: V4 是字符串，V3.1 是对象
        raw_signal = data.get("signal", "")
        if isinstance(raw_signal, dict):
            signal = Signal(
                immediate=raw_signal.get("immediate", ""),
                this_week=raw_signal.get("this_week", ""),
                this_month=raw_signal.get("this_month", ""),
            )
        else:
            signal = raw_signal  # V4: 一句话字符串

        return Article(
            metadata=metadata,
            title=title,
            date=date,
            summary=summary,
            sections=sections,
            cover="",  # 使用默认封面
            author="ZeroRealm AI",
            tags=[source],
            # v2 fields
            trend=data.get("trend", ""),
            data_point=data_point,
            opinion=data.get("opinion", ""),
            discussion=data.get("discussion", ""),
            tomorrow=data.get("tomorrow", []),
            # v3 fields
            heat_index=heat_index,
            # v3.1 fields
            counter_view=data.get("counter_view", ""),
            signal=signal,
            # v4 fields
            signal_no=int(data.get("signal_no", issue)),
            ceo_action=data.get("ceo_action", []),
            industry_temp=industry_temp,
            prediction=prediction,
            exclusive_data=data.get("exclusive_data", {}),
            # v4.2 fields
            ceo_radar=data.get("ceo_radar", []),
            opportunity=data.get("opportunity", ""),
            risk=data.get("risk", ""),
            one_chart=data.get("one_chart", {}),
            # v4.3 fields
            decision=data.get("decision", {}),
            watchlist=data.get("watchlist", []),
            # v4.4 fields
            first_principle=data.get("first_principle", {}),
        )
