"""Self-serve growth ops templates and professional employment boundaries.

Interview / one-to-one outreach templates are retired while the founder remains
employed at a smart-cabinet company.
"""

from __future__ import annotations

from typing import Any


PROFESSIONAL_BOUNDARIES = {
    "id": "founder_employment_boundaries_v1",
    "title": "创始人在职职业边界（智能柜公司任职期间）",
    "rules": [
        "不使用现任公司内部经营数据。",
        "不使用现任公司客户名单。",
        "不使用未公开案例。",
        "不使用内部流程截图。",
        "不引用同事观点作为对外材料。",
        "不以雇主名义发言。",
        "示例仅用公开资料、合成数据或匿名通用场景。",
    ],
    "forbidden_asks": [
        "一对一联系",
        "加微信",
        "预约访谈",
        "提供公司或点位身份",
        "有效运营商交流线索",
    ],
}

CONVERSION_FUNNEL = {
    "id": "organic_self_serve_v1",
    "steps": [
        "公开内容",
        "关注公众号",
        "回复「复盘表」",
        "自助使用周经营复盘工具",
    ],
    "allowed_extra": "工具页公开订阅经营清单（可选）",
    "cta_zh": (
        "关注公众号后回复「复盘表」，自助打开智能柜周经营复盘工具；"
        "可在工具页公开订阅经营清单"
    ),
}

SELF_SERVE_CHECKLIST = {
    "id": "self_serve_ops_checklist_v1",
    "title": "公开内容自助转化检查清单",
    "items": [
        "文末唯一 CTA 指向周复盘工具或引导回复「复盘表」",
        "未要求加微信、一对一联系、访谈或公司/点位身份",
        "未使用现任公司内部数据、客户名单、未公开案例、内部截图或同事观点",
        "未以雇主名义发言；示例为公开/合成/匿名通用场景",
        "可保留公开订阅入口，但不作为访谈前置条件",
    ],
}


def empty_public_distribution_slots(
    *, week_label: str, count: int = 4
) -> list[dict[str, Any]]:
    """Return empty public-distribution review slots (no personal outreach)."""
    if count < 3 or count > 5:
        raise ValueError("weekly public distribution slots must be between 3 and 5")
    return [
        {
            "slot": idx,
            "week": week_label,
            "surface": "",
            "piece_id": "",
            "why_relevant": "",
            "ask": "公开内容自检 / 关键词「复盘表」路径 / 工具页自助（择一核对）",
            "status": "empty",
            "notes": "勿填写公司/点位身份或个人联系方式；无内容则保持空白。",
        }
        for idx in range(1, count + 1)
    ]


# Backward-compatible alias used by older tests / imports.
def empty_target_account_slots(*, week_label: str, count: int = 4) -> list[dict[str, Any]]:
    return empty_public_distribution_slots(week_label=week_label, count=count)


def build_outreach_pack(
    *,
    week1_label: str = "2026-W33",
    week2_label: str = "2026-W34",
    slots_per_week: int = 4,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "professional_boundaries": PROFESSIONAL_BOUNDARIES,
        "conversion_funnel": CONVERSION_FUNNEL,
        "self_serve_checklist": SELF_SERVE_CHECKLIST,
        "weekly_public_distribution_slots": {
            week1_label: empty_public_distribution_slots(
                week_label=week1_label, count=slots_per_week
            ),
            week2_label: empty_public_distribution_slots(
                week_label=week2_label, count=slots_per_week
            ),
        },
        # Keep key for callers that still read weekly_target_slots.
        "weekly_target_slots": {
            week1_label: empty_public_distribution_slots(
                week_label=week1_label, count=slots_per_week
            ),
            week2_label: empty_public_distribution_slots(
                week_label=week2_label, count=slots_per_week
            ),
        },
        "rules": [
            "转化链路：公开内容 → 关注公众号 → 回复「复盘表」→ 自助周复盘工具。",
            "允许公开订阅；禁止一对一联系、加微信、访谈、索取公司或点位身份。",
            "遵守创始人在职职业边界；不记录有效运营商交流线索目标。",
            "每周 3–5 个公开分发自检槽位，默认空值，不预填虚构对象。",
        ],
    }


def render_outreach_markdown(pack: dict[str, Any]) -> str:
    boundaries = pack["professional_boundaries"]
    funnel = pack["conversion_funnel"]
    checklist = pack["self_serve_checklist"]
    lines = [
        "# 自助转化模板与职业边界",
        "",
        "## 规则",
        "",
    ]
    for rule in pack["rules"]:
        lines.append(f"- {rule}")

    lines.extend(["", f"## 职业边界 · {boundaries['title']}", ""])
    for rule in boundaries["rules"]:
        lines.append(f"- {rule}")
    lines.append("")
    lines.append("禁用请求：")
    for item in boundaries["forbidden_asks"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 转化链路", ""])
    lines.append(" → ".join(funnel["steps"]))
    lines.append("")
    lines.append(f"- 允许附加：{funnel['allowed_extra']}")
    lines.append(f"- CTA：{funnel['cta_zh']}")

    lines.extend(["", f"## 检查清单 · {checklist['title']}", ""])
    for item in checklist["items"]:
        lines.append(f"- [ ] {item}")

    lines.extend(["", "## 公开分发自检槽位", ""])
    for week, slots in pack["weekly_public_distribution_slots"].items():
        lines.append(f"### {week}")
        lines.append("")
        lines.append("| 槽位 | 公开面 | 内容 ID | 核对项 | 状态 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for slot in slots:
            lines.append(
                f"| {slot['slot']} |  |  | {slot['ask']} | {slot['status']} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
