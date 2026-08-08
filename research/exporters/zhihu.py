"""Export a Zhihu manual publishing package (no auto-publish)."""

from __future__ import annotations

import json
from pathlib import Path

from research.models import CaseStudy, IndustrySignal, ResearchBrief, SourceDocument
from research.serialization import serialize_source


class ZhihuExportError(ValueError):
    """Raised when a Zhihu package cannot be generated."""


def _canonical(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def build_zhihu_body(
    brief: ResearchBrief,
    *,
    signals: list[IndustrySignal] | None = None,
    cases: list[CaseStudy] | None = None,
    counter_view: str = "",
) -> str:
    """Build a Zhihu-oriented markdown body: answer first, keep sources at end."""
    signals = signals or []
    cases = cases or []
    lines = [
        f"# {brief.title}",
        "",
        brief.summary,
        "",
    ]
    if signals:
        lines.append("## 关键发生了什么")
        for signal in signals:
            lines.extend(
                [
                    f"### {signal.title}",
                    signal.summary,
                    f"**为什么重要：** {signal.why_it_matters}",
                    f"**ZeroRealm 判断：** {signal.judgment}",
                    "",
                ]
            )
    if cases:
        lines.append("## 案例怎么做")
        for case in cases:
            lines.extend(
                [
                    f"### {case.title}",
                    f"- 问题：{case.problem}",
                    f"- 方案：{case.solution}",
                    f"- 运行方式：{case.how_it_works}",
                    "",
                ]
            )
            if case.public_results:
                lines.append("- 公开结果：" + "；".join(case.public_results))
            if case.limitations:
                lines.append("- 不能照搬的条件：" + "；".join(case.limitations))
            lines.append("")
    lines.append("## 反方观点与边界")
    lines.append(counter_view or "任何运营动作都受点位、SKU 结构和补货半径约束，不能把单点经验直接外推。")
    lines.extend(
        [
            "",
            "---",
            "",
            "零域 ZeroRealm：面向智能柜与终端运营的公开研究笔记。",
            "",
        ]
    )
    return "\n".join(lines)


def export_zhihu_package(
    brief: ResearchBrief,
    output_root: str | Path,
    *,
    signals: list[IndustrySignal] | None = None,
    cases: list[CaseStudy] | None = None,
    sources: list[SourceDocument] | None = None,
    topics: list[str] | None = None,
    counter_view: str = "",
) -> Path:
    """Write a deterministic Zhihu package under dist/channels/zhihu/<slug>/."""
    if not brief.slug or ".." in brief.slug or "/" in brief.slug:
        raise ZhihuExportError(f"unsafe brief slug: {brief.slug!r}")

    package_dir = Path(output_root) / brief.slug
    package_dir.mkdir(parents=True, exist_ok=True)

    body = build_zhihu_body(
        brief, signals=signals, cases=cases, counter_view=counter_view
    )
    excerpt = brief.summary[:120]
    source_payload = [serialize_source(source) for source in sorted(sources or [], key=lambda s: s.id)]
    topic_payload = sorted(topics or ["智能柜", "无人零售", "即时零售"])
    metadata = {
        "briefId": brief.id,
        "slug": brief.slug,
        "title": brief.title,
        "channel": "zhihu",
        "autoPublish": False,
        "template": "zhihu_answer",
    }
    cover_prompt = (
        "中文智能零售研究配图：智能柜补货场景，真实运营氛围，无文字无 Logo，16:9。"
    )

    files = {
        "title.txt": brief.title + "\n",
        "body.md": body if body.endswith("\n") else body + "\n",
        "excerpt.txt": excerpt + "\n",
        "topics.json": _canonical(topic_payload),
        "sources.json": _canonical(source_payload),
        "metadata.json": _canonical(metadata),
        "cover-prompt.txt": cover_prompt + "\n",
    }
    for name, text in files.items():
        (package_dir / name).write_text(text, encoding="utf-8", newline="\n")
    return package_dir
