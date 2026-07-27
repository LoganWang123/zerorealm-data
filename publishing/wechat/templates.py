"""微信公众号排版模板 V4（内联 CSS）.

微信仅支持内联 style，不支持 <style> 标签和外部 CSS。
V4: 行业决策解释器模式
- 新增 CEO Action / 行业温度 / 独家数据 / 预测 / Signal品牌
- sections 改为统一列表（不再分子板块）
- Insight 不再用固定标签，改为自然段落
- 互动区改为选择题格式
"""

# 主色 / 强调色
PRIMARY = "#1a1a2e"
ACCENT = "#4a90d9"
LIGHT_BG = "#f7f8fa"
INSIGHT_BG = "#f0f7ff"
INSIGHT_BORDER = "#b8d4f0"
GREEN = "#2e7d32"
GREEN_BG = "#e8f5e9"
ORANGE = "#e65100"


def title_header(title: str, date: str) -> str:
    """标题区域."""
    return (
        f'<h1 style="margin:0 0 4px;font-size:20px;font-weight:bold;color:{PRIMARY};'
        f'line-height:1.4;">'
        f"{title}</h1>"
        f'<p style="margin:0 0 16px;font-size:13px;color:#999;">{date}</p>'
    )


def intro_block() -> str:
    """开头引导语（新读者友好 + SEO关键词）."""
    return (
        f'<p style="margin:0 0 20px;font-size:13px;color:#999;line-height:1.6;'
        f'text-align:center;">'
        f'「零域日报」每日精选智能柜·无人零售·即时零售·AI零售行业动态，<br/>'
        f'由 ZeroRealm AI 智能聚合+分析师洞察，工作日早 8 点更新。</p>'
    )


# ============================================================
# V4 新增模块
# ============================================================


def ceo_action_block(actions: list[str]) -> str:
    """✅ CEO今日行动（V4新增，放最前面，1分钟看完）."""
    if not actions:
        return ""
    items_html = "".join(
        f'<p style="margin:0 0 10px;font-size:15px;color:#1b5e20;line-height:1.6;">'
        f'<span style="display:inline-block;width:20px;height:20px;margin-right:8px;'
        f'border:2px solid {GREEN};border-radius:4px;text-align:center;'
        f'line-height:18px;font-size:12px;color:{GREEN};vertical-align:middle;">✓</span>'
        f"{action}</p>"
        for action in actions
    )
    return (
        f'<div style="margin:0 0 24px;padding:16px 18px;'
        f'background:{GREEN_BG};border-radius:10px;border:1px solid #a5d6a7;">'
        f'<p style="margin:0 0 12px;font-size:15px;font-weight:bold;color:{GREEN};">'
        f"✅ CEO 今日行动</p>"
        f"{items_html}"
        f'<p style="margin:8px 0 0;font-size:12px;color:#66bb6a;">'
        f"⏱ 1分钟看完，今天就知道该做什么</p>"
        f"</div>"
    )


def ceo_radar_block(items: list[str]) -> str:
    """🚨 CEO Radar（V4.2新增，本周必须关注）."""
    if not items:
        return ""
    items_html = "".join(
        f'<p style="margin:0 0 8px;font-size:14px;color:#333;line-height:1.5;">'
        f'<span style="color:#e53935;font-weight:bold;">{i+1}.</span> {item}</p>'
        for i, item in enumerate(items)
    )
    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:#fff3e0;border-radius:10px;border:1px solid #ffcc80;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#e65100;">'
        f"🚨 CEO Radar · 本周必须关注</p>"
        f"{items_html}"
        f"</div>"
    )


def decision_block(decision: dict) -> str:
    """🎯 Decision（V4.3新增，角色化决策）."""
    if not decision:
        return ""
    roles = [
        ("🏪 运营商", decision.get("operators", "")),
        ("🔧 设备商", decision.get("device_makers", "")),
        ("🏷️ 品牌方", decision.get("brands", "")),
        ("💰 投资人", decision.get("investors", "")),
    ]
    rows_html = "".join(
        f'<p style="margin:0 0 8px;font-size:14px;color:#333;line-height:1.5;">'
        f'<strong>{label}：</strong>{action}</p>'
        for label, action in roles if action
    )
    if not rows_html:
        return ""
    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:#e8f5e9;border-radius:10px;border:1px solid #a5d6a7;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:{GREEN};">'
        f"🎯 今日 Decision</p>"
        f"{rows_html}"
        f"</div>"
    )


def watchlist_block(items) -> str:
    """👁 ZeroRealm Watchlist（V4.5: 带Trigger）."""
    if not items:
        return ""
    rows_html = ""
    for item in items:
        if isinstance(item, dict):
            name = item.get("item", "")
            trigger = item.get("trigger", "")
            trigger_html = (
                f' <span style="font-size:11px;color:#e65100;">'
                f'Trigger: {trigger}</span>' if trigger else ""
            )
            rows_html += (
                f'<p style="margin:0 0 6px;font-size:13px;color:#333;">'
                f'• {name}{trigger_html}</p>'
            )
        else:
            rows_html += (
                f'<p style="margin:0 0 6px;font-size:13px;color:#333;">• {item}</p>'
            )
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:{PRIMARY};">'
        f"👁 ZeroRealm Watchlist</p>"
        f"{rows_html}"
        f"</div>"
    )


def first_principle_block(no: int, content: str) -> str:
    """💎 ZeroRealm Principle（V4.4新增，行业底层规律）."""
    if not content:
        return ""
    return (
        f'<div style="margin:28px 0;padding:18px;text-align:center;'
        f'background:linear-gradient(135deg,#1a1a2e 0%,#2d3561 100%);'
        f'border-radius:10px;">'
        f'<p style="margin:0 0 6px;font-size:11px;color:#aaa;letter-spacing:2px;">'
        f"💎 ZeroRealm Principle #{no:03d}</p>"
        f'<p style="margin:0;font-size:16px;font-weight:bold;color:#fff;'
        f'line-height:1.6;">{content}</p>'
        f"</div>"
    )


def opportunity_risk_block(opportunity: str, risk: str) -> str:
    """💡 Opportunity + ⚠️ Risk（V4.2新增）."""
    parts = []
    if opportunity:
        parts.append(
            f'<p style="margin:0 0 8px;font-size:14px;color:#1b5e20;line-height:1.6;">'
            f'<strong>💡 机会：</strong>{opportunity}</p>'
        )
    if risk:
        parts.append(
            f'<p style="margin:0;font-size:14px;color:#b71c1c;line-height:1.6;">'
            f'<strong>⚠️ 风险：</strong>{risk}</p>'
        )
    if not parts:
        return ""
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;border:1px solid #e0e0e0;">'
        + "".join(parts)
        + f"</div>"
    )


def one_chart_block(chart_data: dict) -> str:
    """📊 One Chart（V4.2新增，文本柱状图）."""
    if not chart_data:
        return ""
    title = chart_data.get("title", "")
    rows = chart_data.get("rows", [])
    if not rows:
        return ""

    rows_html = ""
    for row in rows:
        label = row.get("label", "")
        value = int(row.get("value", 0))
        filled = min(round(value / 10), 10)
        bar = "█" * filled + "░" * (10 - filled)
        if value >= 70:
            color = "#e53935"
        elif value >= 40:
            color = "#ff9800"
        else:
            color = "#42a5f5"
        rows_html += (
            f'<p style="margin:0 0 6px;font-size:13px;color:#555;">'
            f'{label} '
            f'<span style="color:{color};font-family:monospace;">{bar}</span> '
            f'<span style="color:{color};font-weight:bold;">{value}</span></p>'
        )

    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:{PRIMARY};">'
        f"📊 {title}</p>"
        f"{rows_html}"
        f"</div>"
    )


def industry_temp_block(temps: dict) -> str:
    """🌡 行业温度（V4新增，替代旧版星级热度指数）.

    用数字 + 文本进度条展示，如：AI热度 ████████░░ 82
    """
    if not temps:
        return ""

    def temp_bar(value: int) -> str:
        """生成文本进度条（10格）."""
        filled = min(round(value / 10), 10)
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        # 颜色：>=70 红色热, >=40 橙色温, <40 蓝色冷
        if value >= 70:
            color = "#e53935"
        elif value >= 40:
            color = "#ff9800"
        else:
            color = "#42a5f5"
        return bar, color

    labels = {
        "ai_retail": "AI零售",
        "instant_retail": "即时零售",
        "smart_cabinet": "智能柜/无人零售",
        "funding": "融资活跃",
        "policy": "政策热度",
    }

    rows_html = ""
    for key, label in labels.items():
        value = temps.get(key, 0)
        bar, color = temp_bar(value)
        rows_html += (
            f'<p style="margin:0 0 8px;font-size:14px;color:#e8e8e8;">'
            f'{label} '
            f'<span style="color:{color};letter-spacing:0px;font-family:monospace;">{bar}</span> '
            f'<span style="color:{color};font-weight:bold;">{value}</span></p>'
        )

    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:linear-gradient(135deg,#1a1a2e 0%,#2d3561 100%);'
        f'border-radius:10px;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#fff;">'
        f"🌡 今日行业温度</p>"
        f"{rows_html}"
        f'<p style="margin:10px 0 0;font-size:11px;color:#8888aa;">'
        f"ZeroRealm Index：综合新闻数量×重要性权重生成</p>"
        f"</div>"
    )


def signal_brand_block(signal_no: int, signal_text: str) -> str:
    """📡 ZeroRealm Signal #XXX（V4.1: 三位数编号）."""
    if not signal_text:
        return ""
    # V4.1: 三位数编号 #003
    no_str = f"#{signal_no:03d}"
    return (
        f'<div style="margin:28px 0;padding:18px;text-align:center;'
        f'border:2px solid {PRIMARY};border-radius:10px;'
        f'background:linear-gradient(135deg,#fafafa 0%,#f0f0f0 100%);">'
        f'<p style="margin:0 0 4px;font-size:11px;color:#999;letter-spacing:2px;">'
        f"📡 ZeroRealm Signal {no_str}</p>"
        f'<p style="margin:0;font-size:17px;font-weight:bold;color:{PRIMARY};'
        f'line-height:1.6;">{signal_text}</p>'
        f"</div>"
    )


def prediction_block(content: str, confidence: int = 0, basis: str = "",
                     confidence_pct: int = 0, drivers: list = None,
                     blockers: list = None, risk_note: str = "") -> str:
    """🔮 ZeroRealm Prediction（V4.5: ✓/✗ 清单）."""
    if not content:
        return ""
    # 置信度
    if confidence_pct > 0:
        filled = min(round(confidence_pct / 10), 10)
        bar = "█" * filled + "□" * (10 - filled)
        conf_html = (
            f'<p style="margin:0 0 8px;font-size:14px;color:#6a1b9a;">'
            f'Confidence <span style="font-family:monospace;">{bar}</span> '
            f'<strong>{confidence_pct}%</strong></p>'
        )
    else:
        stars = "⭐" * min(confidence, 5) + "☆" * max(0, 5 - confidence)
        conf_html = f'<p style="margin:0 0 8px;font-size:13px;color:#9c27b0;">置信度：{stars}</p>'

    # ✓/✗ 清单
    checklist_html = ""
    if drivers:
        for d in drivers:
            checklist_html += (
                f'<p style="margin:0 0 4px;font-size:13px;color:#2e7d32;">{d}</p>'
            )
    if blockers:
        for b in blockers:
            checklist_html += (
                f'<p style="margin:0 0 4px;font-size:13px;color:#c62828;">{b}</p>'
            )
    if checklist_html:
        checklist_html = f'<div style="margin:8px 0;padding:8px 12px;background:#fafafa;border-radius:6px;">{checklist_html}</div>'

    # 风险备注
    risk_html = ""
    rn = risk_note or basis
    if rn:
        risk_html = (
            f'<p style="margin:8px 0 0;font-size:12px;color:#7b1fa2;">'
            f"⚠️ {rn}</p>"
        )

    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:#f3e5f5;border-radius:8px;border:1px solid #ce93d8;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:#6a1b9a;">'
        f"🔮 ZeroRealm Prediction</p>"
        f'<p style="margin:0 0 6px;font-size:15px;color:#444;line-height:1.7;">'
        f"{content}</p>"
        f"{conf_html}"
        f"{checklist_html}"
        f"{risk_html}"
        f"</div>"
    )


def exclusive_data_block(data: dict) -> str:
    """📊 ZeroRealm Exclusive（V4新增，独家监测数据）."""
    if not data:
        return ""

    sources = data.get("sources_monitored", 0)
    total = data.get("total_items", 0)
    industry = data.get("industry_events", 0)
    funding = data.get("funding_events", 0)
    partnership = data.get("partnership_events", 0)
    new_products = data.get("new_products", 0)
    hot_keywords = data.get("hot_keywords", [])
    one_line = data.get("one_line", "")

    # 数据网格
    stats = [
        (f"{sources}", "监测源"),
        (f"{total}", "资讯采集"),
        (f"{industry}", "行业动态"),
        (f"{funding}", "融资事件"),
        (f"{partnership}", "合作事件"),
        (f"{new_products}", "新品/服务"),
    ]
    stats_html = "".join(
        f'<div style="display:inline-block;width:30%;text-align:center;'
        f'margin-bottom:12px;vertical-align:top;">'
        f'<p style="margin:0;font-size:20px;font-weight:bold;color:{ACCENT};">{num}</p>'
        f'<p style="margin:2px 0 0;font-size:11px;color:#999;">{label}</p>'
        f"</div>"
        for num, label in stats
    )

    # 热词
    keywords_html = ""
    if hot_keywords:
        kw_spans = "".join(
            f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:3px 10px;'
            f'background:#e3f2fd;color:#1565c0;font-size:12px;border-radius:12px;'
            f'font-weight:bold;">{kw}</span>'
            for kw in hot_keywords
        )
        keywords_html = (
            f'<p style="margin:12px 0 0;font-size:12px;color:#666;">'
            f"🔥 今日热词：{kw_spans}</p>"
        )

    # 一句话
    one_line_html = ""
    if one_line:
        one_line_html = (
            f'<p style="margin:12px 0 0;font-size:14px;color:#333;'
            f'line-height:1.6;font-style:italic;">"{one_line}"</p>'
        )

    return (
        f'<div style="margin:28px 0;padding:18px;'
        f'background:linear-gradient(135deg,#e8eaf6 0%,#f3e5f5 100%);'
        f'border-radius:10px;border:1px solid #c5cae9;">'
        f'<p style="margin:0 0 14px;font-size:14px;font-weight:bold;color:#283593;">'
        f"📊 ZeroRealm Exclusive · 今日监测</p>"
        f'<div style="text-align:center;">{stats_html}</div>'
        f"{keywords_html}"
        f"{one_line_html}"
        f"</div>"
    )


# ============================================================
# 保留模块（V4修改）
# ============================================================


def trend_block(trend_text: str) -> str:
    """📈 今日趋势块."""
    if not trend_text:
        return ""
    return (
        f'<div style="margin:0 0 24px;padding:16px 18px;'
        f'background:linear-gradient(135deg,#1a1a2e 0%,#2d3561 100%);'
        f'border-radius:10px;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:#fff;">'
        f"📈 今日趋势</p>"
        f'<p style="margin:0;font-size:15px;color:#e8e8e8;line-height:1.7;">'
        f"{trend_text}</p>"
        f"</div>"
    )


def summary_block(items: list[str]) -> str:
    """📌 今日三分钟."""
    lis = "".join(
        f'<li style="margin-bottom:8px;font-size:15px;color:#444;line-height:1.5;">{item}</li>'
        for item in items
    )
    return (
        f'<div style="margin:16px 0 28px;padding:16px 18px;'
        f"background:{LIGHT_BG};border-radius:8px;border:1px solid #eef0f2;\">"
        f'<p style="margin:0 0 10px;font-size:15px;font-weight:bold;color:{PRIMARY};">'
        f"📌 今日三分钟</p>"
        f'<ul style="margin:0;padding-left:18px;list-style:disc;">{lis}</ul>'
        f"</div>"
    )


def section_header(title: str) -> str:
    """板块标题样式：左 4px 蓝竖线 + 18px 加粗."""
    return (
        f'<h2 style="margin:32px 0 16px;padding-left:12px;'
        f"border-left:4px solid {ACCENT};"
        f'font-size:18px;font-weight:bold;color:{PRIMARY};">'
        f"{title}</h2>"
    )


def news_item(title: str, excerpt: str, source_name: str, index: int,
              source_url: str = "", insight: str = "",
              importance: str = "", tags: list[str] | None = None,
              angle: str = "", impact: dict | None = None,
              level: str = "") -> str:
    """单条新闻样式 V4.1：重要度 + 角度 + 标题 + 摘要 + 深度分析 + 影响对象 + Tags + 来源."""
    # 重要度标记
    importance_badge = ""
    if importance == "A":
        importance_badge = (
            f'<span style="display:inline-block;margin-right:6px;padding:1px 6px;'
            f'background:#e53935;color:#fff;font-size:11px;border-radius:3px;'
            f'vertical-align:middle;">今日必看</span>'
        )
    elif importance == "B":
        importance_badge = (
            f'<span style="display:inline-block;margin-right:6px;padding:1px 6px;'
            f'background:{ACCENT};color:#fff;font-size:11px;border-radius:3px;'
            f'vertical-align:middle;">重要</span>'
        )

    # 角度标记（V4新增）
    angle_badge = ""
    if angle:
        angle_map = {
            "为什么发生": "🔍 为什么",
            "谁最受影响": "👥 谁受影响",
            "三个月后会怎样": "⏳ 三个月后",
            "谁会赚钱": "💰 谁赚钱",
            "谁应该行动": "🎯 谁行动",
            "反面思考": "🔄 反面",
        }
        angle_label = angle_map.get(angle, f"💡 {angle}")
        angle_badge = (
            f'<span style="display:inline-block;margin-right:6px;padding:1px 6px;'
            f'background:#7b1fa2;color:#fff;font-size:11px;border-radius:3px;'
            f'vertical-align:middle;">{angle_label}</span>'
        )

    # 来源行
    if source_url:
        source_line = (
            f'<a style="font-size:12px;color:{ACCENT};text-decoration:none;" '
            f'href="{source_url}">📎 {source_name} → 原文</a>'
        )
    else:
        source_line = f'<span style="font-size:12px;color:#999;">来源：{source_name}</span>'

    # Insight 块（V4：直接渲染自然段落，不做 regex 替换）
    insight_html = ""
    if insight:
        # 将换行转为 <br/>，保留自然段落格式
        formatted = insight.replace("\n", "<br/>")
        insight_html = (
            f'<div style="margin:10px 0;padding:14px 16px;'
            f'background:{INSIGHT_BG};border-left:3px solid {ACCENT};'
            f'border-radius:0 6px 6px 0;">'
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:bold;color:{ACCENT};">'
            f"💡 ZeroRealm 深度分析</p>"
            f'<p style="margin:0;font-size:14px;color:#444;line-height:1.9;">'
            f"{formatted}</p>"
            f"</div>"
        )

    # Tags 行
    tags_html = ""
    if tags:
        tag_spans = "".join(
            f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;'
            f'background:#eef2f7;color:#555;font-size:11px;border-radius:10px;">'
            f"#{t}</span>"
            for t in tags
        )
        tags_html = f'<p style="margin:8px 0 0;">{tag_spans}</p>'

    # 影响对象（V4.1新增）
    impact_html = ""
    if impact and isinstance(impact, dict):
        def stars(n: int) -> str:
            return "★" * min(int(n), 5) + "☆" * max(0, 5 - int(n))
        impact_labels = [
            ("运营商", impact.get("operators", 0)),
            ("设备商", impact.get("device_makers", 0)),
            ("品牌方", impact.get("brands", 0)),
            ("投资人", impact.get("investors", 0)),
        ]
        impact_items = "".join(
            f'<span style="display:inline-block;margin-right:12px;font-size:12px;color:#555;">'
            f'{label} <span style="color:#ff9800;">{stars(val)}</span></span>'
            for label, val in impact_labels if val > 0
        )
        if impact_items:
            impact_html = (
                f'<p style="margin:8px 0 0;font-size:12px;color:#888;">'
                f'🎯 影响：{impact_items}</p>'
            )

    return (
        f'<div style="margin-bottom:28px;padding-bottom:24px;'
        f'border-bottom:1px dashed #e8e8e8;">'
        f'<p style="margin:0 0 8px;font-size:16px;font-weight:bold;color:#222;">'
        f"{importance_badge}{angle_badge}{index}. {title}</p>"
        f'<p style="margin:0 0 6px;font-size:15px;color:#555;line-height:1.7;">'
        f"{excerpt}</p>"
        f"{insight_html}"
        f"{impact_html}"
        f"{tags_html}"
        f'<p style="margin:8px 0 0;">{source_line}</p>'
        f"</div>"
    )


def data_point_block(number: str, label: str, interpretation: str) -> str:
    """📊 今日数据块."""
    if not number:
        return ""
    return (
        f'<div style="margin:28px 0;padding:18px;text-align:center;'
        f'background:{LIGHT_BG};border-radius:8px;">'
        f'<p style="margin:0 0 4px;font-size:28px;font-weight:bold;color:{ACCENT};">'
        f"{number}</p>"
        f'<p style="margin:0 0 8px;font-size:13px;color:#999;">{label}</p>'
        f'<p style="margin:0;font-size:14px;color:#555;line-height:1.5;">'
        f"{interpretation}</p>"
        f"</div>"
    )


def counter_view_block(text: str) -> str:
    """🔄 不同视角."""
    if not text:
        return ""
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:#f3f0ff;border-radius:8px;border:1px solid #d1c4e9;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:#4a148c;">'
        f"🔄 Counter View</p>"
        f'<p style="margin:0;font-size:15px;color:#444;line-height:1.7;">'
        f"{text}</p>"
        f"</div>"
    )


def discussion_block(question: str) -> str:
    """💬 今日互动（V4升级：选择题格式）."""
    if not question:
        return ""
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:#fff8f0;border-radius:8px;border:1px solid #ffe0b2;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:{ORANGE};">'
        f"💬 今日互动</p>"
        f'<p style="margin:0;font-size:15px;color:#555;line-height:1.8;">'
        f"{question}</p>"
        f"</div>"
    )


def tomorrow_block(items: list[str]) -> str:
    """📅 明日关注."""
    if not items:
        return ""
    lis = "".join(
        f'<li style="margin-bottom:6px;font-size:14px;color:#555;">{item}</li>'
        for item in items
    )
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:{PRIMARY};">'
        f"📅 明日关注</p>"
        f'<ul style="margin:0;padding-left:18px;list-style:circle;">{lis}</ul>'
        f"</div>"
    )


def footer(author: str) -> str:
    """尾部：品牌签名 + CTA."""
    return (
        f'<div style="margin-top:36px;padding:20px 16px;'
        f'background:{LIGHT_BG};border-radius:8px;text-align:center;">'
        f'<p style="font-size:14px;color:#666;margin:0 0 8px;">'
        f"—— 零域日报 · {author} ——</p>"
        f'<p style="font-size:13px;color:#999;margin:0 0 12px;">'
        f"智能柜 · 无人零售 · 即时零售 · AI零售 · 行业决策参考</p>"
        f'<p style="font-size:14px;color:{ACCENT};margin:0;">'
        f"👆 觉得有用？<strong>转发</strong>给同行朋友，关注不迷路</p>"
        f"</div>"
    )


# ============================================================
# 废弃模块（保留兼容，不再使用）
# ============================================================


def heat_index_block(ai_retail: int = 3, instant_retail: int = 3,
                     smart_cabinet: int = 3, funding: int = 2) -> str:
    """[DEPRECATED] 旧版星级热度指数，V4已替换为 industry_temp_block."""
    def stars(n: int) -> str:
        return "★" * min(n, 5) + "☆" * max(0, 5 - n)

    rows = [
        ("AI零售", ai_retail),
        ("即时零售", instant_retail),
        ("智能柜/无人零售", smart_cabinet),
        ("融资活跃度", funding),
    ]
    items_html = "".join(
        f'<p style="margin:0 0 6px;font-size:14px;color:#e8e8e8;">'
        f'{label} <span style="color:#ffd700;letter-spacing:1px;">{stars(n)}</span></p>'
        for label, n in rows
    )
    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:linear-gradient(135deg,#1a1a2e 0%,#2d3561 100%);'
        f'border-radius:10px;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#fff;">'
        f"📈 今日指数</p>"
        f"{items_html}"
        f"</div>"
    )


def opinion_block(opinion: str) -> str:
    """[DEPRECATED] 旧版 ZeroRealm View，V4已合并到 signal_brand_block."""
    if not opinion:
        return ""
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'border:2px solid {PRIMARY};border-radius:8px;text-align:center;">'
        f'<p style="margin:0 0 6px;font-size:12px;color:#999;">🎯 ZeroRealm View</p>'
        f'<p style="margin:0;font-size:16px;font-weight:bold;color:{PRIMARY};'
        f'line-height:1.5;">{opinion}</p>'
        f"</div>"
    )


def signal_block(immediate: str = "", this_week: str = "", this_month: str = "") -> str:
    """[DEPRECATED] 旧版行动信号，V4已替换为 ceo_action_block."""
    rows = []
    if immediate:
        rows.append(
            f'<p style="margin:0 0 8px;font-size:14px;color:#c62828;">'
            f'<strong>⚡ 立即：</strong>{immediate}</p>'
        )
    if this_week:
        rows.append(
            f'<p style="margin:0 0 8px;font-size:14px;color:#e65100;">'
            f'<strong>📅 本周：</strong>{this_week}</p>'
        )
    if this_month:
        rows.append(
            f'<p style="margin:0;font-size:14px;color:#555;">'
            f'<strong>🔭 本月：</strong>{this_month}</p>'
        )
    if not rows:
        return ""
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:#fff3e0;border-radius:8px;border:1px solid #ffcc80;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#e65100;">'
        f"🚦 行动信号</p>"
        + "".join(rows)
        + f"</div>"
    )
