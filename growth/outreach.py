"""Interview / public-case templates and empty outreach slots."""

from __future__ import annotations

from typing import Any


INTERVIEW_TEMPLATE = {
    "id": "operator_interview_v1",
    "title": "智能柜运营商访谈提纲（公开前需授权）",
    "duration_minutes": 30,
    "privacy_rules": [
        "未经书面/明确许可，不公开姓名、公司名、点位地址或可识别信息。",
        "公开案例只使用对方确认可披露的聚合口径。",
        "拒绝录音时改为要点笔记，不虚构引语。",
    ],
    "sections": [
        {
            "name": "背景",
            "questions": [
                "目前管理大约多少台柜？主要场景？",
                "本周你最常看的经营数字是哪 1–2 个？",
            ],
        },
        {
            "name": "五指标周复盘",
            "questions": [
                "如果只能保留五个过程指标，你会留哪五个？为什么？",
                "哪一个指标最容易“看起来好看但实际没帮到补货/选品”？",
            ],
        },
        {
            "name": "缺货排查",
            "questions": [
                "最近一次严重缺货是怎么发现的？",
                "补货前你实际会先查哪几步？",
            ],
        },
        {
            "name": "运营决策",
            "questions": [
                "上周你做过的一个保留/调货/撤点决策，依据是什么？",
                "如果重来，你会多要哪一条证据？",
            ],
        },
        {
            "name": "公开意愿",
            "questions": [
                "是否愿意以匿名或具名形式出现在公开案例？",
                "哪些数字绝对不能写进公开文？",
            ],
        },
    ],
}


PUBLIC_CASE_TEMPLATE = {
    "id": "public_case_v1",
    "title": "公开案例写作模板（需授权）",
    "required_fields": [
        "permission_status",
        "anonymization_level",
        "context",
        "metric_before_after",
        "action_taken",
        "stop_rule",
        "source_of_truth",
        "operator_quote_approved",
    ],
    "field_notes": {
        "permission_status": "pending | granted | denied（无授权不得发布）",
        "anonymization_level": "full_name | company_only | anonymous_role",
        "context": "场景、柜量级（区间）、时间窗；禁止写入精确地址。",
        "metric_before_after": "仅写对方确认可披露的指标变化；标注内部实验口径。",
        "action_taken": "具体经营动作（补货/调货/撤点等）。",
        "stop_rule": "什么情况下停止该动作。",
        "source_of_truth": "对方系统截图/口述聚合；不收录用户 PII。",
        "operator_quote_approved": "true 仅当原话已确认；否则留空，禁止虚构。",
    },
    "forbidden": [
        "虚构公司名、人名或案例结果",
        "把小样本访谈写成行业基准",
        "在知乎/微信混用未授权细节",
    ],
}


def empty_target_account_slots(*, week_label: str, count: int = 4) -> list[dict[str, Any]]:
    """Return empty outreach slots; names must be filled by the operator."""
    if count < 3 or count > 5:
        raise ValueError("weekly target account slots must be between 3 and 5")
    return [
        {
            "slot": idx,
            "week": week_label,
            "account_or_org": "",
            "contact_channel": "",
            "why_relevant": "",
            "ask": "访谈 / 公开案例授权 / 订阅经营清单（择一）",
            "status": "empty",
            "notes": "勿虚构名称；无合适对象则保持空白并在周复盘说明。",
        }
        for idx in range(1, count + 1)
    ]


def build_outreach_pack(
    *,
    week1_label: str = "2026-W33",
    week2_label: str = "2026-W34",
    slots_per_week: int = 4,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "interview_template": INTERVIEW_TEMPLATE,
        "public_case_template": PUBLIC_CASE_TEMPLATE,
        "weekly_target_slots": {
            week1_label: empty_target_account_slots(
                week_label=week1_label, count=slots_per_week
            ),
            week2_label: empty_target_account_slots(
                week_label=week2_label, count=slots_per_week
            ),
        },
        "rules": [
            "每周 3–5 个目标账户槽位，默认空值，不预填虚构名称。",
            "访谈与公开案例必须先授权。",
            "外联结果只记聚合意向数到实验台账漏斗槽位。",
        ],
    }


def render_outreach_markdown(pack: dict[str, Any]) -> str:
    interview = pack["interview_template"]
    case = pack["public_case_template"]
    lines = [
        "# 访谈 / 公开案例模板与目标账户槽位",
        "",
        "## 规则",
        "",
    ]
    for rule in pack["rules"]:
        lines.append(f"- {rule}")

    lines.extend(["", f"## 访谈提纲 · {interview['title']}", ""])
    for rule in interview["privacy_rules"]:
        lines.append(f"- {rule}")
    lines.append("")
    for section in interview["sections"]:
        lines.append(f"### {section['name']}")
        lines.append("")
        for question in section["questions"]:
            lines.append(f"- {question}")
        lines.append("")

    lines.extend(["", f"## 公开案例模板 · {case['title']}", ""])
    for field in case["required_fields"]:
        note = case["field_notes"].get(field, "")
        lines.append(f"- `{field}`: {note}")
    lines.append("")
    lines.append("禁止：")
    for item in case["forbidden"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 每周目标账户槽位（空）", ""])
    for week, slots in pack["weekly_target_slots"].items():
        lines.append(f"### {week}")
        lines.append("")
        lines.append("| # | 账户/组织 | 渠道 | 相关原因 | 诉求 | 状态 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for slot in slots:
            lines.append(
                f"| {slot['slot']} |  |  |  | {slot['ask']} | {slot['status']} |"
            )
        lines.append("")
    return "\n".join(lines)
