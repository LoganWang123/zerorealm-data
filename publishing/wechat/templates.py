"""微信公众号排版模板 V6（内联 CSS）.

微信仅支持内联 style，不支持 <style> 标签和外部 CSS。
V6: 新零售行业情报官模式
- 内容分层：2篇深度（Why Now）+ 快讯列表
- Decision 五要素：Action + Budget + KPI + Owner + Deadline
- 新增 Today's Number / Industry Map / ZeroRealm Lens / Prediction Score
- Watchlist 升级为看板（状态灯）
- 三屏首页结构
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
    """🚨 CEO Radar（旧版兼容，纯列表）."""
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


def ceo_radar_unified_block(focus: list, prediction_check: list,
                            tomorrow: list, tracking: list = None) -> str:
    """🚨 CEO Radar（V9: 持续追踪 + Prediction Validation）."""
    # V9: 优先使用 tracking 格式
    if tracking and isinstance(tracking, list):
        return _ceo_radar_tracking(tracking, prediction_check)
    # 兼容 V7/V8 格式
    if not focus and not prediction_check and not tomorrow:
        return ""
    parts_html = ""
    if focus:
        items_html = "".join(
            f'<p style="margin:0 0 6px;font-size:14px;color:#333;line-height:1.5;">'
            f'<span style="color:#e53935;font-weight:bold;">{i+1}.</span> {item}</p>'
            for i, item in enumerate(focus)
        )
        parts_html += items_html
    if prediction_check:
        status_icons = {"hit": "✅", "miss": "❌", "pending": "⏳"}
        pred_html = "".join(
            f'<span style="display:inline-block;margin-right:12px;font-size:12px;'
            f'color:#555;">{status_icons.get(p.get("status", "pending"), "⏳")}'
            f' {p.get("item", "")}</span>'
            for p in prediction_check if isinstance(p, dict)
        )
        if pred_html:
            parts_html += (
                f'<p style="margin:10px 0 0;font-size:12px;color:#888;'
                f'border-top:1px dashed #ffe0b2;padding-top:8px;">'
                f'🔮 预测验证：{pred_html}</p>'
            )
    if tomorrow:
        tm_html = " · ".join(tomorrow)
        parts_html += (
            f'<p style="margin:8px 0 0;font-size:12px;color:#888;">'
            f'📅 明日：{tm_html}</p>'
        )
    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:#fff3e0;border-radius:10px;border:1px solid #ffcc80;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#e65100;">'
        f"🚨 CEO Radar</p>"
        f"{parts_html}"
        f"</div>"
    )


def _ceo_radar_tracking(tracking: list, prediction_check: list) -> str:
    """🚨 CEO Radar（V9: 持续追踪模式，带状态灯+天数）."""
    status_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    rows_html = ""
    for t in tracking:
        if isinstance(t, dict):
            item = t.get("item", "")
            status = t.get("status", "yellow")
            day = t.get("day", 1)
            icon = status_icons.get(status, "🟡")
            rows_html += (
                f'<p style="margin:0 0 8px;font-size:14px;color:#333;'
                f'line-height:1.5;">'
                f'{icon} <strong>{item}</strong> '
                f'<span style="font-size:12px;color:#888;">'
                f'持续第{day}天</span></p>'
            )
    # Prediction Validation
    pred_html = ""
    if prediction_check:
        pv_icons = {"hit": "✅", "miss": "❌", "pending": "⏳"}
        for p in prediction_check:
            if isinstance(p, dict):
                pv_icons.get(p.get("status", "pending"), "⏳")
                pred_html += (
                    f'<span style="display:inline-block;margin-right:12px;'
                    f'font-size:12px;color:#555;">'
                    f'{pv_icons.get(p.get("status", "pending"), "⏳")}'
                    f' {p.get("item", "")}</span>'
                )
    if pred_html:
        rows_html += (
            f'<p style="margin:10px 0 0;font-size:12px;color:#888;'
            f'border-top:1px dashed #ffe0b2;padding-top:8px;">'
            f'🔮 预测验证：{pred_html}</p>'
        )
    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:#fff3e0;border-radius:10px;border:1px solid #ffcc80;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#e65100;">'
        f"🚨 CEO Radar · 持续追踪</p>"
        f"{rows_html}"
        f"</div>"
    )


def decision_block(decision: dict) -> str:
    """🎯 ZeroRealm Decision（V8: Evidence → Action → KPI → Risk → Confidence）."""
    if not decision:
        return ""
    roles = [
        ("🏪 运营商", decision.get("operators", {})),
        ("🔧 设备商", decision.get("device_makers", {})),
        ("🏷️ 品牌方", decision.get("brands", {})),
        ("💰 投资人", decision.get("investors", {})),
    ]
    rows_html = ""
    for label, data in roles:
        if isinstance(data, dict) and (data.get("action") or data.get("goal")):
            evidence = data.get("evidence", "")
            why_today = data.get("why_today", "")
            action = data.get("action", "")
            kpi = data.get("kpi", "")
            risk = data.get("risk", "")
            confidence_pct = data.get("confidence_pct", 0)
            rows_html += (
                f'<div style="margin:0 0 12px;padding:10px 12px;'
                f'background:#f1f8e9;border-radius:6px;">'
                f'<p style="margin:0 0 4px;font-size:14px;font-weight:bold;'
                f'color:#333;">{label}</p>'
            )
            if evidence:
                rows_html += (
                    f'<p style="margin:0 0 3px;font-size:13px;color:#555;'
                    f'line-height:1.5;">📌 Evidence：{evidence}</p>'
                )
            if why_today:
                rows_html += (
                    f'<p style="margin:0 0 3px;font-size:13px;color:#e65100;'
                    f'line-height:1.5;">⏰ Why Today：{why_today}</p>'
                )
            if action:
                rows_html += (
                    f'<p style="margin:0 0 3px;font-size:13px;color:#555;'
                    f'line-height:1.5;">⚡ Action：{action}</p>'
                )
            if kpi:
                rows_html += (
                    f'<p style="margin:0 0 3px;font-size:13px;color:#2e7d32;'
                    f'line-height:1.5;">✅ KPI：{kpi}</p>'
                )
            if risk:
                rows_html += (
                    f'<p style="margin:0 0 3px;font-size:12px;color:#c62828;'
                    f'line-height:1.5;">⚠️ Risk：{risk}</p>'
                )
            if confidence_pct:
                filled = min(round(confidence_pct / 10), 10)
                bar = "█" * filled + "□" * (10 - filled)
                rows_html += (
                    f'<p style="margin:4px 0 0;font-size:12px;color:#6a1b9a;">'
                    f'Confidence <span style="font-family:monospace;">{bar}</span> '
                    f'<strong>{confidence_pct}%</strong></p>'
                )
            # 兼容 V7/V6 旧格式
            if not evidence and not confidence_pct:
                goal = data.get("goal", "")
                how = data.get("how", "")
                if goal:
                    rows_html += (
                        f'<p style="margin:0 0 3px;font-size:13px;color:#555;'
                        f'line-height:1.5;">🎯 目标：{goal}</p>'
                    )
                if how:
                    rows_html += (
                        f'<p style="margin:0 0 3px;font-size:13px;color:#555;'
                        f'line-height:1.5;">🛠 How：{how}</p>'
                    )
            rows_html += '</div>'
        elif isinstance(data, str) and data:
            rows_html += (
                f'<p style="margin:0 0 8px;font-size:14px;color:#333;line-height:1.5;">'
                f'<strong>{label}：</strong>{data}</p>'
            )
    if not rows_html:
        return ""
    return (
        f'<div style="margin:0 0 24px;padding:14px 18px;'
        f'background:#e8f5e9;border-radius:10px;border:1px solid #a5d6a7;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:{GREEN};">'
        f"🎯 ZeroRealm Decision</p>"
        f"{rows_html}"
        f"</div>"
    )


def overseas_signal_block(trend: str, why_china: str) -> str:
    """🌍 海外信号（V5.0新增）."""
    if not trend:
        return ""
    why_html = ""
    if why_china:
        why_html = (
            f'<p style="margin:6px 0 0;font-size:13px;color:#1565c0;">'
            f'🇨🇳 对中国意味着：{why_china}</p>'
        )
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:#e3f2fd;border-radius:8px;border:1px solid #90caf9;">'
        f'<p style="margin:0 0 6px;font-size:14px;font-weight:bold;color:#1565c0;">'
        f"🌍 海外信号</p>"
        f'<p style="margin:0;font-size:14px;color:#333;line-height:1.6;">{trend}</p>'
        f"{why_html}"
        f"</div>"
    )


def watchlist_block(items) -> str:
    """👁 ZeroRealm Watchlist（V6: 看板模式，带状态灯）."""
    if not items:
        return ""
    status_icons = {
        "green": "🟢",
        "yellow": "🟡",
        "red": "🔴",
    }
    rows_html = ""
    for item in items:
        if isinstance(item, dict):
            # V6 新格式：company + event + status
            company = item.get("company", "")
            event = item.get("event", "")
            status = item.get("status", "yellow")
            icon = status_icons.get(status, "🟡")
            # 兼容旧格式 item + trigger
            if not company and item.get("item"):
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
                    f'<p style="margin:0 0 8px;font-size:13px;color:#333;'
                    f'line-height:1.5;">'
                    f'{icon} <strong>{company}</strong> · {event}</p>'
                )
        else:
            rows_html += (
                f'<p style="margin:0 0 6px;font-size:13px;color:#333;">• {item}</p>'
            )
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;border:1px solid #e0e0e0;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:{PRIMARY};">'
        f"👁 ZeroRealm Watchlist</p>"
        f"{rows_html}"
        f'<p style="margin:8px 0 0;font-size:11px;color:#999;">'
        f"🟢推进中 🟡观察 🔴暂无动作</p>"
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
              level: str = "", why_now: list | None = None,
              spread_line: str = "", prediction: dict | None = None,
              score: dict | None = None) -> str:
    """单条新闻样式 V9：支持 spread_line + insight + 内嵌 prediction + score."""
    # 重要度标记
    importance_badge = ""
    if level == "core" or importance == "A":
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

    # Insight 块（V6：支持 spread_line + Why Now + 因果链）
    insight_html = ""
    if insight or spread_line or why_now:
        inner_parts = []
        # spread_line（一句话传播）
        if spread_line:
            inner_parts.append(
                f'<p style="margin:0 0 10px;font-size:15px;color:#1a1a2e;'
                f'font-weight:bold;line-height:1.6;font-style:italic;">'
                f'“{spread_line}”</p>'
            )
        # Why Now 模块
        if why_now and isinstance(why_now, list):
            why_items = "".join(
                f'<p style="margin:0 0 4px;font-size:13px;color:#444;'
                f'line-height:1.5;padding-left:4px;">'
                f'<span style="color:{ACCENT};font-weight:bold;">'
                f'{chr(9312 + i)}</span> {reason}</p>'
                for i, reason in enumerate(why_now[:5])
            )
            inner_parts.append(
                f'<div style="margin:8px 0;padding:10px 12px;'
                f'background:#fff8e1;border-radius:6px;border:1px solid #ffe082;">'
                f'<p style="margin:0 0 6px;font-size:12px;font-weight:bold;'
                f'color:#f57f17;">⚡ Why Now</p>'
                f'{why_items}</div>'
            )
        # 因果链分析（insight 主体）
        if insight:
            formatted = insight.replace("\n", "<br/>")
            inner_parts.append(
                f'<p style="margin:8px 0 0;font-size:14px;color:#444;'
                f'line-height:1.9;">{formatted}</p>'
            )
        insight_html = (
            f'<div style="margin:10px 0;padding:14px 16px;'
            f'background:{INSIGHT_BG};border-left:3px solid {ACCENT};'
            f'border-radius:0 6px 6px 0;">'
            f'<p style="margin:0 0 6px;font-size:12px;font-weight:bold;color:{ACCENT};">'
            f"💡 ZeroRealm 深度分析</p>"
            f'{"" .join(inner_parts)}'
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

    # 影响对象
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

    # V9: 内嵌 Prediction 渲染
    prediction_html = ""
    if prediction and isinstance(prediction, dict) and prediction.get("content"):
        p_content = prediction.get("content", "")
        p_pct = int(prediction.get("confidence_pct", 0))
        p_evidence = prediction.get("evidence", [])
        p_watch = prediction.get("watch", "")
        filled = min(round(p_pct / 10), 10)
        bar = "█" * filled + "□" * (10 - filled)
        ev_html = ""
        if p_evidence:
            ev_items = "".join(
                f'<span style="display:inline-block;margin-right:10px;'
                f'font-size:12px;color:#555;">• {e}</span>'
                for e in p_evidence[:3]
            )
            ev_html = (
                f'<p style="margin:6px 0 0;font-size:12px;color:#888;">'
                f'Evidence：{ev_items}</p>'
            )
        watch_html = ""
        if p_watch:
            watch_html = (
                f'<p style="margin:4px 0 0;font-size:12px;color:#e65100;">'
                f'👁 Watch：{p_watch}</p>'
            )
        prediction_html = (
            f'<div style="margin:10px 0;padding:10px 14px;'
            f'background:#f3e5f5;border-radius:6px;border:1px solid #ce93d8;">'
            f'<p style="margin:0 0 4px;font-size:13px;color:#6a1b9a;'
            f'font-weight:bold;">🔮 Prediction：{p_content}</p>'
            f'<p style="margin:0 0 4px;font-size:13px;color:#6a1b9a;">'
            f'Confidence <span style="font-family:monospace;">{bar}</span> '
            f'<strong>{p_pct}%</strong></p>'
            f'{ev_html}{watch_html}</div>'
        )

    # V9: ZeroRealm Score 渲染
    score_html = ""
    if score and isinstance(score, dict):
        def _stars(n: int) -> str:
            return "★" * min(int(n), 5) + "☆" * max(0, 5 - int(n))
        score_labels = [
            ("战略价值", score.get("strategic", 0)),
            ("商业价值", score.get("commercial", 0)),
            ("落地速度", score.get("landing", 0)),
            ("可信度", score.get("credibility", 0)),
        ]
        score_items = "".join(
            f'<span style="display:inline-block;margin-right:14px;font-size:12px;'
            f'color:#555;">{label} '
            f'<span style="color:#ff9800;">{_stars(val)}</span></span>'
            for label, val in score_labels if val > 0
        )
        if score_items:
            score_html = (
                f'<div style="margin:8px 0;padding:8px 12px;'
                f'background:#fafafa;border-radius:6px;border:1px solid #eee;">'
                f'<p style="margin:0;font-size:12px;color:#888;">'
                f'📊 ZeroRealm Score：{score_items}</p></div>'
            )

    return (
        f'<div style="margin-bottom:28px;padding-bottom:24px;'
        f'border-bottom:1px dashed #e8e8e8;">'
        f'<p style="margin:0 0 8px;font-size:16px;font-weight:bold;color:#222;">'
        f"{importance_badge}{angle_badge}{index}. {title}</p>"
        f'<p style="margin:0 0 6px;font-size:15px;color:#555;line-height:1.7;">'
        f"{excerpt}</p>"
        f"{insight_html}"
        f"{prediction_html}"
        f"{score_html}"
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
# V6/V7/V8 新增模块
# ============================================================


def signal_matrix_block(items: list) -> str:
    """📊 Signal Matrix（V8兼容，V9已升级为 trend_v9_block）."""
    if not items:
        return ""
    rows_html = ""
    for item in items:
        if isinstance(item, dict):
            topic = item.get("topic", "")
            stars = int(item.get("stars", 0))
            star_str = "★" * min(stars, 5) + "☆" * max(0, 5 - stars)
            color = "#e53935" if stars >= 5 else "#ff9800" if stars >= 4 else "#42a5f5"
            rows_html += (
                f'<p style="margin:0 0 6px;font-size:14px;color:#333;'
                f'line-height:1.5;">'
                f'{topic} <span style="color:{color};letter-spacing:1px;">'
                f'{star_str}</span></p>'
            )
    if not rows_html:
        return ""
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;border:1px solid #e0e0e0;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;'
        f'color:{PRIMARY};">📊 Signal Matrix · 今日行业热度</p>'
        f"{rows_html}"
        f"</div>"
    )


def trend_v9_block(items: list) -> str:
    """📈 ZeroRealm Trend（V9: Bloomberg玩法，星级+方向+连续天数）."""
    if not items:
        return ""
    direction_icons = {"up": "↑", "down": "↓", "flat": "→"}
    direction_colors = {"up": "#ff6b6b", "down": "#64b5f6", "flat": "#aaaaaa"}
    rows_html = ""
    for item in items:
        if isinstance(item, dict):
            topic = item.get("topic", "")
            stars = int(item.get("stars", 0))
            direction = item.get("direction", "flat")
            streak = int(item.get("streak", 0))
            star_str = "★" * min(stars, 5) + "☆" * max(0, 5 - stars)
            d_icon = direction_icons.get(direction, "→")
            d_color = direction_colors.get(direction, "#999")
            streak_html = ""
            if streak > 1 and direction != "flat":
                label = "连续上涨" if direction == "up" else "连续下降"
                streak_html = (
                    f' <span style="font-size:11px;color:{d_color};">'
                    f'{label}第{streak}天</span>'
                )
            rows_html += (
                f'<p style="margin:0 0 8px;font-size:14px;color:#e8e8e8;'
                f'line-height:1.5;">'
                f'{topic} '
                f'<span style="color:#ffd700;letter-spacing:1px;">{star_str}</span> '
                f'<span style="color:{d_color};font-weight:bold;">{d_icon}</span>'
                f'{streak_html}</p>'
            )
    if not rows_html:
        return ""
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:linear-gradient(135deg,#1a1a2e 0%,#2d3561 100%);'
        f'border-radius:10px;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;color:#fff;">'
        f"📈 ZeroRealm Trend</p>"
        f'<div style="color:#e8e8e8;">{rows_html}</div>'
        f"</div>"
    )


def alpha_block(data: dict) -> str:
    """🔥 ZeroRealm Alpha（V8: 独家数据）."""
    if not data:
        return ""
    data_point = data.get("data_point", "")
    source = data.get("source", "")
    sample = data.get("sample", "")
    window = data.get("window", "")
    if not data_point:
        return ""
    meta_parts = []
    if source:
        meta_parts.append(source)
    if sample:
        meta_parts.append(f'样本：{sample}')
    if window:
        meta_parts.append(window)
    meta_html = ""
    if meta_parts:
        meta_html = (
            f'<p style="margin:8px 0 0;font-size:11px;color:#999;">'
            f'{" | ".join(meta_parts)}</p>'
        )
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:linear-gradient(135deg,#fff3e0 0%,#fbe9e7 100%);'
        f'border-radius:10px;border:1px solid #ffcc80;">'
        f'<p style="margin:0 0 8px;font-size:14px;font-weight:bold;'
        f'color:#e65100;">🔥 ZeroRealm Alpha</p>'
        f'<p style="margin:0;font-size:15px;color:#333;line-height:1.7;'
        f'font-weight:bold;">{data_point}</p>'
        f"{meta_html}"
        f"</div>"
    )


def data_corner_block(data: dict) -> str:
    """📊 数据角（V7: 合并 Today's Number + 监测数据）."""
    if not data:
        return ""
    parts_html = ""

    # Today's Number
    tn = data.get("todays_number", {})
    if tn and isinstance(tn, dict) and tn.get("number"):
        comparison_html = ""
        if tn.get("comparison"):
            comparison_html = (
                f'<p style="margin:6px 0 0;font-size:12px;color:#888;">'
                f'📊 {tn["comparison"]}</p>'
            )
        parts_html += (
            f'<div style="text-align:center;margin-bottom:14px;">'
            f'<p style="margin:0;font-size:32px;font-weight:bold;color:{ACCENT};">'
            f'{tn["number"]}</p>'
            f'<p style="margin:2px 0 0;font-size:13px;color:#555;font-weight:bold;">'
            f'{tn.get("label", "")}</p>'
            f'{comparison_html}</div>'
        )

    # 监测概览
    sources = data.get("sources_monitored", 0)
    total = data.get("total_items", 0)
    events = data.get("industry_events", 0)
    if sources or total or events:
        parts_html += (
            f'<p style="margin:0 0 8px;font-size:13px;color:#666;text-align:center;">'
            f'📡 监测 {sources} 源 · 采集 {total} 条 · 行业动态 {events} 条</p>'
        )

    # 热词
    hot_keywords = data.get("hot_keywords", [])
    if hot_keywords:
        kw_spans = "".join(
            f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:3px 10px;'
            f'background:#e3f2fd;color:#1565c0;font-size:12px;border-radius:12px;'
            f'font-weight:bold;">{kw}</span>'
            for kw in hot_keywords
        )
        parts_html += (
            f'<p style="margin:8px 0 0;font-size:12px;color:#666;text-align:center;">'
            f'🔥 {kw_spans}</p>'
        )

    if not parts_html:
        return ""
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:linear-gradient(135deg,#e8eaf6 0%,#e3f2fd 100%);'
        f'border-radius:10px;border:1px solid #c5cae9;">'
        f'<p style="margin:0 0 12px;font-size:14px;font-weight:bold;'
        f'color:#283593;text-align:center;">📊 数据角</p>'
        f"{parts_html}"
        f"</div>"
    )


def quick_news_list(items: list) -> str:
    """⚡ 快讯紧凑列表（V7: 每条新闻 + 一句判断）."""
    if not items:
        return ""
    rows_html = ""
    for i, item in enumerate(items, 1):
        if isinstance(item, dict):
            title = item.get("title", "")
            excerpt = item.get("excerpt", "")
            verdict = item.get("verdict", "")
            source_name = item.get("source_name", "")
            source_url = item.get("source_url", "")
            source_html = ""
            if source_url:
                source_html = (
                    f' <a style="font-size:11px;color:{ACCENT};text-decoration:none;"'
                    f' href="{source_url}">[{source_name}]</a>'
                )
            elif source_name:
                source_html = f' <span style="font-size:11px;color:#999;">[{source_name}]</span>'
            rows_html += (
                f'<p style="margin:0 0 4px;font-size:14px;color:#333;'
                f'line-height:1.6;padding-left:4px;">'
                f'<span style="color:{ACCENT};font-weight:bold;margin-right:6px;">'
                f'{i}.</span>'
                f'<strong>{title}</strong>'
                f'{f" — {excerpt}" if excerpt else ""}'
                f'{source_html}</p>'
            )
            # V7: 一句判断
            if verdict:
                rows_html += (
                    f'<p style="margin:0 0 12px;font-size:13px;color:#666;'
                    f'padding-left:22px;font-style:italic;line-height:1.5;">'
                    f'→ {verdict}</p>'
                )
        elif isinstance(item, str):
            rows_html += (
                f'<p style="margin:0 0 10px;font-size:14px;color:#333;'
                f'line-height:1.6;padding-left:4px;">'
                f'<span style="color:{ACCENT};font-weight:bold;margin-right:6px;">'
                f'{i}.</span>{item}</p>'
            )
    return (
        f'<div style="margin:0 0 28px;padding:14px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;border:1px solid #eef0f2;">'
        f"{rows_html}"
        f"</div>"
    )


def todays_number_block(number: str, label: str, why_important: str,
                        comparison: str) -> str:
    """🔢 Today's Number（V6兼容，V7已合并入 data_corner_block）."""
    if not number:
        return ""
    comparison_html = ""
    if comparison:
        comparison_html = (
            f'<p style="margin:8px 0 0;font-size:13px;color:#666;'
            f'line-height:1.5;">📊 {comparison}</p>'
        )
    return (
        f'<div style="margin:28px 0;padding:20px 18px;text-align:center;'
        f'background:linear-gradient(135deg,#e8eaf6 0%,#e3f2fd 100%);'
        f'border-radius:10px;border:1px solid #c5cae9;">'
        f'<p style="margin:0 0 2px;font-size:11px;color:#999;letter-spacing:2px;">'
        f"TODAY'S NUMBER</p>"
        f'<p style="margin:0 0 6px;font-size:36px;font-weight:bold;color:{ACCENT};">'
        f"{number}</p>"
        f'<p style="margin:0 0 8px;font-size:14px;color:#333;font-weight:bold;">'
        f"{label}</p>"
        f'<p style="margin:0;font-size:13px;color:#555;line-height:1.5;">'
        f"{why_important}</p>"
        f"{comparison_html}"
        f"</div>"
    )


def industry_map_block(today_position: str, chain: list) -> str:
    """🗺️ Industry Map（V6: 行业地图，垂直链条）."""
    if not chain:
        return ""
    rows_html = ""
    for node in chain:
        is_today = "←" in str(node) or (today_position and today_position in str(node))
        if is_today:
            rows_html += (
                f'<p style="margin:0 0 4px;font-size:14px;text-align:center;">'
                f'<span style="display:inline-block;padding:4px 14px;'
                f'background:#e53935;color:#fff;border-radius:14px;'
                f'font-weight:bold;font-size:13px;">{node}</span></p>'
            )
        else:
            rows_html += (
                f'<p style="margin:0 0 4px;font-size:13px;text-align:center;'
                f'color:#666;">{node}</p>'
            )
        rows_html += (
            f'<p style="margin:0 0 4px;text-align:center;color:#ccc;'
            f'font-size:12px;">↓</p>'
        )
    # 去掉最后一个箭头
    rows_html = rows_html.rsplit('<p style="margin:0 0 4px;text-align:center;color:#ccc;', 1)[0]
    return (
        f'<div style="margin:28px 0;padding:16px 18px;'
        f'background:{LIGHT_BG};border-radius:8px;border:1px solid #e0e0e0;">'
        f'<p style="margin:0 0 12px;font-size:14px;font-weight:bold;'
        f'color:{PRIMARY};text-align:center;">🗺️ Industry Map</p>'
        f"{rows_html}"
        f"</div>"
    )


def zerorealm_lens_block(logic_chain: list, one_line: str) -> str:
    """🔍 ZeroRealm Lens（V6: 零域视角，行业演进逻辑链）."""
    if not logic_chain and not one_line:
        return ""
    chain_html = ""
    if logic_chain:
        nodes = " → ".join(str(n) for n in logic_chain)
        chain_html = (
            f'<p style="margin:0 0 10px;font-size:15px;color:#e8e8e8;'
            f'line-height:1.8;text-align:center;font-weight:bold;">'
            f"{nodes}</p>"
        )
    one_line_html = ""
    if one_line:
        one_line_html = (
            f'<p style="margin:0;font-size:14px;color:#aaa;'
            f'line-height:1.6;text-align:center;font-style:italic;">'
            f"{one_line}</p>"
        )
    return (
        f'<div style="margin:28px 0;padding:18px;'
        f'background:linear-gradient(135deg,#1a1a2e 0%,#2d3561 100%);'
        f'border-radius:10px;">'
        f'<p style="margin:0 0 10px;font-size:11px;color:#aaa;'
        f'letter-spacing:2px;text-align:center;">🔍 ZeroRealm Lens</p>'
        f"{chain_html}"
        f"{one_line_html}"
        f"</div>"
    )


def prediction_score_block(history: list, accuracy_pct: int = 0) -> str:
    """📈 Prediction Score（V6: 预测复盘）."""
    if not history and not accuracy_pct:
        return ""
    status_icons = {
        "hit": "✅",
        "miss": "❌",
        "pending": "⏳",
    }
    rows_html = ""
    if history:
        for item in history:
            if isinstance(item, dict):
                name = item.get("item", "")
                status = item.get("status", "pending")
                icon = status_icons.get(status, "⏳")
                rows_html += (
                    f'<p style="margin:0 0 6px;font-size:13px;color:#333;'
                    f'line-height:1.5;">'
                    f'{icon} {name}</p>'
                )
    accuracy_html = ""
    if accuracy_pct > 0:
        accuracy_html = (
            f'<p style="margin:10px 0 0;font-size:14px;color:#6a1b9a;'
            f'font-weight:bold;text-align:center;">'
            f'历史预测准确率：{accuracy_pct}%</p>'
        )
    return (
        f'<div style="margin:28px 0;padding:14px 18px;'
        f'background:#faf5ff;border-radius:8px;border:1px solid #e1bee7;">'
        f'<p style="margin:0 0 10px;font-size:14px;font-weight:bold;'
        f'color:#6a1b9a;">📈 Prediction Score</p>'
        f"{rows_html}"
        f"{accuracy_html}"
        f"</div>"
    )


def why_now_block(reasons: list) -> str:
    """⚡ Why Now 独立模块（V6: 可单独调用）."""
    if not reasons:
        return ""
    items_html = "".join(
        f'<p style="margin:0 0 6px;font-size:14px;color:#444;'
        f'line-height:1.5;padding-left:4px;">'
        f'<span style="color:#f57f17;font-weight:bold;">'
        f'{chr(9312 + i)}</span> {reason}</p>'
        for i, reason in enumerate(reasons[:5])
    )
    return (
        f'<div style="margin:12px 0;padding:12px 14px;'
        f'background:#fff8e1;border-radius:6px;border:1px solid #ffe082;">'
        f'<p style="margin:0 0 8px;font-size:12px;font-weight:bold;'
        f'color:#f57f17;">⚡ Why Now — 为什么是今天？</p>'
        f"{items_html}"
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
