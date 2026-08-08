"""Golden editorial style benchmark vs shadow draft (no fake total score)."""

from __future__ import annotations

from dataclasses import dataclass, field

from content.ai_style import detect_ai_style_patterns
from content.generator import StructuredDraft
from content.style_profile import load_style_profile


GOLDEN_TRAITS = {
    "opening_directness": "问题导向开场，避免宏大叙事",
    "business_relevance": "紧扣终端经营/智能柜运营",
    "evidence_density": "指标与证据清楚",
    "paragraph_concision": "短段落，少空话",
    "unsupported_claims": "不伪造数字/无证据结论",
    "ai_style_patterns": "少模板句",
    "actionability": "对运营有可观察指标",
    "fact_inference_boundary": "事实与推断边界清楚",
}


@dataclass
class BenchmarkDiff:
    dimension: str
    assessment: str  # STRONGER | SIMILAR | WEAKER
    note: str

    def to_dict(self) -> dict:
        return {"dimension": self.dimension, "assessment": self.assessment, "note": self.note}


def compare_to_golden_style(draft: StructuredDraft, *, golden_excerpt: str = "") -> dict:
    profile = load_style_profile()
    text = "\n".join(
        [draft.title, draft.summary]
        + [f"{s.title}\n{s.body}" for s in draft.sections]
        + [s.text for s in draft.statements]
    )
    diffs: list[BenchmarkDiff] = []

    opening = (draft.sections[0].body if draft.sections else draft.summary) or ""
    if any(p.replace("……", "")[:4] in opening for p in profile.opening_forbid_patterns):
        diffs.append(BenchmarkDiff("opening_directness", "WEAKER", "Opening looks template/grand"))
    elif any(k in opening for k in ("问题", "运营", "指标", "缺货", "GMV", "经营")):
        diffs.append(BenchmarkDiff("opening_directness", "SIMILAR", "Opens near operating problem"))
    else:
        diffs.append(BenchmarkDiff("opening_directness", "WEAKER", "Opening not problem-led"))

    if any(k in text for k in ("智能柜", "缺货", "补货", "库存", "运营", "动销")):
        diffs.append(BenchmarkDiff("business_relevance", "SIMILAR", "Retail/ops vocabulary present"))
    else:
        diffs.append(BenchmarkDiff("business_relevance", "WEAKER", "Weak operating relevance"))

    fact_n = sum(1 for s in draft.statements if s.statement_type == "FACT" and s.claim_ids)
    if fact_n >= 1:
        diffs.append(BenchmarkDiff("evidence_density", "SIMILAR", f"FACT with claims={fact_n}"))
    else:
        diffs.append(BenchmarkDiff("evidence_density", "WEAKER", "Missing cited FACT"))

    avg_len = 0
    bodies = [s.body for s in draft.sections if s.body]
    if bodies:
        avg_len = sum(len(b) for b in bodies) / len(bodies)
    if avg_len and avg_len <= 280:
        diffs.append(BenchmarkDiff("paragraph_concision", "SIMILAR", f"avg_section_len={int(avg_len)}"))
    else:
        diffs.append(BenchmarkDiff("paragraph_concision", "WEAKER", f"avg_section_len={int(avg_len)}"))

    diffs.append(
        BenchmarkDiff(
            "unsupported_claims",
            "SIMILAR" if all(s.claim_ids or s.statement_type != "FACT" for s in draft.statements) else "WEAKER",
            "Checked FACT claim binding only; Hard Gate is authoritative",
        )
    )

    ai_w = detect_ai_style_patterns(text, profile)
    diffs.append(
        BenchmarkDiff(
            "ai_style_patterns",
            "SIMILAR" if len(ai_w) <= 1 else "WEAKER",
            f"style_warnings={len(ai_w)}",
        )
    )

    if any(k in text for k in ("指标", "缺货率", "库存准确率", "补货", "观察", "验证")):
        diffs.append(BenchmarkDiff("actionability", "SIMILAR", "Mentions observable metrics/actions"))
    else:
        diffs.append(BenchmarkDiff("actionability", "WEAKER", "Low actionability"))

    if any(k in text for k in ("不能说明", "仍需", "待验证", "边界", "并不等于", "不足以")) or any(
        s.statement_type in {"INFERENCE", "HYPOTHESIS"} for s in draft.statements
    ):
        diffs.append(BenchmarkDiff("fact_inference_boundary", "SIMILAR", "Boundary language present"))
    else:
        diffs.append(BenchmarkDiff("fact_inference_boundary", "WEAKER", "Boundary under-specified"))

    return {
        "golden_slug": (profile.golden_benchmark or {}).get("slug"),
        "golden_traits": GOLDEN_TRAITS,
        "diffs": [d.to_dict() for d in diffs],
        "note": "No aggregate numeric score. Golden article is style benchmark only, not to be republished.",
        "golden_excerpt_used": bool(golden_excerpt),
    }
