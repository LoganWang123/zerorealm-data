"""微信公众号排版模板（内联 CSS）.

微信仅支持内联 style，不支持 <style> 标签和外部 CSS。
"""

# 主色 / 强调色
PRIMARY = "#1a1a2e"
ACCENT = "#4a90d9"

# 板块标题映射
SECTION_TITLES = {
    "industry": "🏭 行业动态",
    "enterprise": "🏢 企业资讯",
    "ai_frontier": "🤖 AI 前沿",
    "policy": "📋 政策法规",
}


def section_header(title: str) -> str:
    """板块标题样式：左 4px 蓝竖线 + 18px 加粗."""
    return (
        f'<h2 style="margin:28px 0 16px;padding-left:12px;'
        f"border-left:4px solid {ACCENT};"
        f'font-size:18px;font-weight:bold;color:{PRIMARY};">'
        f"{title}</h2>"
    )


def news_item(title: str, excerpt: str, source_name: str, index: int) -> str:
    """单条新闻样式."""
    return (
        f'<div style="margin-bottom:20px;">'
        f'<p style="margin:0 0 6px;font-size:16px;font-weight:bold;color:#222;">'
        f"{index}. {title}</p>"
        f'<p style="margin:0 0 4px;font-size:15px;color:#555;line-height:1.6;">'
        f"{excerpt}</p>"
        f'<p style="margin:0;font-size:13px;color:#999;">'
        f"来源：{source_name}</p>"
        f"</div>"
    )


def summary_block(items: list[str]) -> str:
    """摘要要点块."""
    lis = "".join(
        f'<li style="margin-bottom:6px;font-size:15px;color:#444;">{item}</li>'
        for item in items
    )
    return (
        f'<div style="margin:16px 0 24px;padding:14px 16px;'
        f"background:#f7f8fa;border-radius:6px;\">"
        f'<p style="margin:0 0 8px;font-size:15px;font-weight:bold;color:{PRIMARY};">'
        f"📌 今日要点</p>"
        f'<ul style="margin:0;padding-left:18px;list-style:disc;">{lis}</ul>'
        f"</div>"
    )


def footer(author: str) -> str:
    """尾部样式."""
    return (
        f'<div style="margin-top:32px;padding-top:16px;'
        f'border-top:1px solid #eee;text-align:center;">'
        f'<p style="font-size:14px;color:#999;margin:0;">'
        f"本文由 {author} 自动生成</p>"
        f'<p style="font-size:13px;color:#bbb;margin:4px 0 0;">'
        f"ZeroRealm AI · 零域智能</p>"
        f"</div>"
    )


def title_header(title: str, date: str) -> str:
    """标题区域."""
    return (
        f'<h1 style="margin:0 0 4px;font-size:22px;font-weight:bold;color:{PRIMARY};">'
        f"{title}</h1>"
        f'<p style="margin:0 0 20px;font-size:14px;color:#999;">{date}</p>'
    )
