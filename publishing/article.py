"""Article 统一内容模型.

定义 Article / ArticleMeta / Lifecycle 等领域对象。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class Lifecycle(Enum):
    """内容生命周期."""

    DRAFT = "draft"
    VALIDATED = "validated"
    RENDERED = "rendered"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class ArticleMeta:
    """Article 元数据."""

    uuid: str  # 确定性生成，幂等判断用
    slug: str  # "daily-2026-07-26"
    source: str  # "daily" / "insight" / "weekly" / "manual"
    issue: int  # 期号
    language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    created_at: str = ""  # ISO 8601
    updated_at: str = ""
    version: int = 1  # 内容模型版本号（迁移用）
    schema_version: int = 1  # Article 结构版本（Parser 迁移用）
    content_revision: int = 1  # 内容修订号（业务层）
    lifecycle: Lifecycle = Lifecycle.DRAFT


@dataclass
class ArticleItem:
    """单条新闻."""

    title: str
    excerpt: str
    source_url: str
    source_name: str
    insight: str = ""  # 💡 ZeroRealm Insight (v2)
    importance: str = ""  # A/B/C (v3)
    confidence: str = ""  # High/Medium/Low (v3.1)
    action: str = ""  # immediate/this_week/observe (v3.1)
    tags: dict | list = field(default_factory=list)  # 两层: {industry, topics} (v3.1)
    angle: str = ""  # 分析角度 (v4): 为什么/谁受影响/三个月后/谁赚钱/谁行动/反面
    level: str = ""  # 层级 (v4.1): core/important/quick
    impact: dict = field(default_factory=dict)  # 影响对象 (v4.1): {operators, device_makers, brands, investors}
    why_it_matters: str = ""  # 为什么重要 (v4.4): 一句话


@dataclass
class ArticleSection:
    """新闻板块."""

    type: str  # industry / enterprise / ai_frontier / policy
    items: list[ArticleItem] = field(default_factory=list)


@dataclass
class DataPoint:
    """今日数据 (v2)."""

    number: str = ""
    label: str = ""
    interpretation: str = ""


@dataclass
class HeatIndex:
    """今日热度指数 (v3)."""

    ai_retail: int = 3
    instant_retail: int = 3
    smart_cabinet: int = 3
    funding: int = 2


@dataclass
class Signal:
    """行动信号 (v3.1). [DEPRECATED in V4, kept for backward compat]"""

    immediate: str = ""
    this_week: str = ""
    this_month: str = ""


@dataclass
class IndustryTemp:
    """行业温度 (v4): 0~100 数字温度."""

    ai_retail: int = 50
    instant_retail: int = 50
    smart_cabinet: int = 50
    funding: int = 30
    policy: int = 30


@dataclass
class Prediction:
    """未来30~90天预测 (v4.1)."""

    content: str = ""
    confidence: int = 3  # 1~5星 (deprecated in v4.1)
    basis: str = ""
    confidence_pct: int = 0  # 置信度百分比 (v4.1)


@dataclass
class Article:
    """统一内容模型 (v4: 行业决策解释器)."""

    metadata: ArticleMeta
    title: str  # "零域日报 No.1"
    date: str  # "2026-07-26"
    summary: list[str] = field(default_factory=list)  # 3 条要点
    sections: list = field(default_factory=list)  # V4: 统一列表或分板块
    cover: str = ""  # 封面图路径
    author: str = "ZeroRealm AI"
    tags: list[str] = field(default_factory=list)
    # v2 fields
    trend: str = ""  # 今日趋势
    data_point: DataPoint = field(default_factory=DataPoint)
    opinion: str = ""  # 🎯 ZeroRealm View [DEPRECATED in V4]
    discussion: str = ""  # 今日互动
    tomorrow: list[str] = field(default_factory=list)  # 明日关注
    # v3 fields
    heat_index: HeatIndex = field(default_factory=HeatIndex)  # [DEPRECATED in V4]
    # v3.1 fields
    counter_view: str = ""  # 不同视角
    signal: str | Signal = field(default_factory=Signal)  # V4: str一句话 / 旧:Signal对象
    # v4 fields
    signal_no: int = 0  # ZeroRealm Signal 编号
    ceo_action: list[str] = field(default_factory=list)  # CEO今日任务
    industry_temp: IndustryTemp = field(default_factory=IndustryTemp)  # 行业温度
    prediction: Prediction = field(default_factory=Prediction)  # 未来30天预测
    exclusive_data: dict = field(default_factory=dict)  # ZeroRealm Exclusive 数据
    # v4.2 fields
    ceo_radar: list[str] = field(default_factory=list)  # CEO Radar
    opportunity: str = ""  # 今日机会
    risk: str = ""  # 今日风险
    one_chart: dict = field(default_factory=dict)  # One Chart
    # v4.3 fields
    decision: dict = field(default_factory=dict)  # 角色化Decision
    watchlist: list[str] = field(default_factory=list)  # 本周监控名单
    # v4.4 fields
    first_principle: dict = field(default_factory=dict)  # ZeroRealm Principle
    # v5.0 fields
    overseas_signal: dict = field(default_factory=dict)  # 海外信号


def generate_uuid(source: str, date: str, issue: int) -> str:
    """确定性 UUID 生成（基于 source + date + issue）.

    同一篇日报无论解析多少次，UUID 始终一致，用于幂等判断。
    """
    raw = f"{source}:{date}:{issue}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
