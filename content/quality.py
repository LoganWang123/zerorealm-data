"""Content quality evaluation — separate from Hard Gate. No fake precision scores."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from content.ai_style import StyleWarning, detect_ai_style_patterns
from content.generator import StructuredDraft
from content.models import ContentCandidate
from content.style_profile import StyleProfile, load_style_profile


class QualityLevel(str, Enum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    WEAK = "WEAK"


class QualityResult(str, Enum):
    PASS = "PASS"
    NEEDS_EDIT = "NEEDS_EDIT"
    FAIL = "FAIL"


DIMENSIONS = (
    "clarity",
    "structure",
    "professionalism",
    "specificity",
    "redundancy",
    "ai_style",
    "evidence_usage",
    "reader_value",
)


@dataclass
class DimensionScore:
    name: str
    level: QualityLevel
    reason: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "level": self.level.value, "reason": self.reason}


@dataclass
class QualityReport:
    content_id: str
    content_type: str
    result: QualityResult
    dimensions: list[DimensionScore] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    recommended_edits: list[str] = field(default_factory=list)
    hard_gate_passed: bool | None = None
    statement_counts: dict = field(default_factory=dict)
    model: str = ""
    prompt_version: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "content_type": self.content_type,
            "result": self.result.value,
            "dimensions": {d.name: {"level": d.level.value, "reason": d.reason} for d in self.dimensions},
            "warnings": list(self.warnings),
            "recommended_edits": list(self.recommended_edits),
            "hard_gate_passed": self.hard_gate_passed,
            "statement_counts": dict(self.statement_counts),
            "model": self.model,
            "prompt_version": self.prompt_version,
            "notes": list(self.notes),
            "scoring_policy": "ordinal_levels_only_no_percent_score",
        }


def _draft_text(draft: StructuredDraft) -> str:
    parts = [draft.title, draft.summary]
    for sec in draft.sections:
        parts.append(sec.title)
        parts.append(sec.body)
    for stmt in draft.statements:
        parts.append(stmt.text)
    return "\n".join(p for p in parts if p)


def _sentence_list(text: str) -> list[str]:
    chunks = re.split(r"[。！？\n]+", text or "")
    return [c.strip() for c in chunks if c.strip()]


class ContentQualityEvaluator:
    """Deterministic editorial quality checks. Optional LLM critique is advisory only."""

    def __init__(self, profile: StyleProfile | None = None):
        self.profile = profile or load_style_profile()

    def evaluate(
        self,
        draft: StructuredDraft,
        *,
        candidate: ContentCandidate | None = None,
        hard_gate_passed: bool | None = None,
        llm_critique: dict | None = None,
    ) -> QualityReport:
        text = _draft_text(draft)
        dims: list[DimensionScore] = []
        warnings: list[dict] = []
        edits: list[str] = []
        notes: list[str] = [
            "Hard Gate judges factual compliance; Quality Evaluator judges editorial value.",
            "No percent/star score is produced.",
        ]

        # clarity
        title_len = len(draft.title or "")
        if 12 <= title_len <= 48:
            dims.append(DimensionScore("clarity", QualityLevel.GOOD, "Title length reasonable"))
        elif 8 <= title_len <= 60:
            dims.append(DimensionScore("clarity", QualityLevel.ACCEPTABLE, "Title length acceptable"))
        else:
            dims.append(DimensionScore("clarity", QualityLevel.WEAK, "Title too short/long"))
            edits.append("调整标题长度，使其更直接指出经营问题")

        # structure
        section_n = len(draft.sections)
        if draft.content_type == "daily":
            if 1 <= section_n <= 4:
                dims.append(DimensionScore("structure", QualityLevel.GOOD, "Daily compact structure"))
            else:
                dims.append(DimensionScore("structure", QualityLevel.WEAK, "Daily should stay ONE SIGNAL / compact"))
                edits.append("Daily 压缩为单一经营信号结构")
        else:
            if 2 <= section_n <= 8:
                dims.append(DimensionScore("structure", QualityLevel.GOOD, "Insight section count ok"))
            elif section_n == 1:
                dims.append(DimensionScore("structure", QualityLevel.ACCEPTABLE, "Single-section insight"))
            else:
                dims.append(DimensionScore("structure", QualityLevel.WEAK, "Structure too thin or sprawling"))

        # professionalism / avoid terms
        avoid_hits = [w for w in self.profile.avoid if w and w in text]
        if not avoid_hits:
            dims.append(DimensionScore("professionalism", QualityLevel.GOOD, "No avoid-list marketing terms"))
        elif len(avoid_hits) <= 2:
            dims.append(
                DimensionScore(
                    "professionalism",
                    QualityLevel.ACCEPTABLE,
                    f"Mild avoid-list hits: {', '.join(avoid_hits)}",
                )
            )
            edits.append("弱化宣传腔词： " + "、".join(avoid_hits))
        else:
            dims.append(
                DimensionScore(
                    "professionalism",
                    QualityLevel.WEAK,
                    f"Avoid-list hits: {', '.join(avoid_hits)}",
                )
            )
            edits.append("删除宏大叙事/营销词")

        # specificity
        digits = len(re.findall(r"\d", text))
        if digits >= 2 or any(s.statement_type == "FACT" for s in draft.statements):
            dims.append(DimensionScore("specificity", QualityLevel.GOOD, "Contains concrete claims/numbers"))
        else:
            dims.append(DimensionScore("specificity", QualityLevel.WEAK, "Too abstract"))
            edits.append("用已验证证据替换空泛表述")

        # redundancy
        sents = _sentence_list(text)
        uniq = set(sents)
        dup_ratio = 1.0 - (len(uniq) / max(1, len(sents)))
        title_in_summary = bool(draft.title and draft.summary and draft.title.strip() == draft.summary.strip())
        if dup_ratio < 0.15 and not title_in_summary:
            dims.append(DimensionScore("redundancy", QualityLevel.GOOD, "Low repetition"))
        elif dup_ratio < 0.35:
            dims.append(DimensionScore("redundancy", QualityLevel.ACCEPTABLE, "Some repetition"))
            edits.append("压缩重复句/标题摘要重复")
        else:
            dims.append(DimensionScore("redundancy", QualityLevel.WEAK, "High repetition"))
            edits.append("删除重复段落与机械总结")

        # ai_style
        style_warnings = detect_ai_style_patterns(text, self.profile)
        warnings.extend(w.to_dict() for w in style_warnings)
        if not style_warnings:
            dims.append(DimensionScore("ai_style", QualityLevel.GOOD, "No strong AI-template patterns"))
        elif len(style_warnings) <= 2:
            dims.append(DimensionScore("ai_style", QualityLevel.ACCEPTABLE, "Mild AI-style patterns"))
            edits.append("改写模板句，开头更直接")
        else:
            dims.append(DimensionScore("ai_style", QualityLevel.WEAK, "Heavy AI-style patterns"))
            edits.append("大幅减少 AI 模板句与机械排比")

        # evidence_usage
        fact_with_claims = sum(1 for s in draft.statements if s.statement_type == "FACT" and s.claim_ids)
        facts = sum(1 for s in draft.statements if s.statement_type == "FACT")
        if facts and fact_with_claims == facts:
            dims.append(DimensionScore("evidence_usage", QualityLevel.GOOD, "All FACT statements cite claims"))
        elif fact_with_claims:
            dims.append(DimensionScore("evidence_usage", QualityLevel.ACCEPTABLE, "Partial claim coverage"))
            edits.append("为所有 FACT 补齐 claim_ids")
        else:
            dims.append(DimensionScore("evidence_usage", QualityLevel.WEAK, "Missing claim citations"))
            edits.append("FACT 必须绑定 verified claim_ids")

        # reader_value
        has_boundary = any(
            k in text for k in ("不能说明", "仍需", "待验证", "边界", "不足以", "并不等于")
        )
        if has_boundary or any(s.statement_type == "INFERENCE" for s in draft.statements):
            dims.append(DimensionScore("reader_value", QualityLevel.GOOD, "Shows operating boundary/value"))
        elif facts:
            dims.append(DimensionScore("reader_value", QualityLevel.ACCEPTABLE, "Informative but thin boundary"))
            edits.append("补一句：证据能说明什么 / 不能说明什么")
        else:
            dims.append(DimensionScore("reader_value", QualityLevel.WEAK, "Low operator value"))

        if llm_critique:
            notes.append("LLM critique is advisory only and does not approve editorial status.")
            for tip in llm_critique.get("recommended_edits") or []:
                if tip not in edits:
                    edits.append(str(tip))

        weak_n = sum(1 for d in dims if d.level is QualityLevel.WEAK)
        good_n = sum(1 for d in dims if d.level is QualityLevel.GOOD)
        if hard_gate_passed is False:
            result = QualityResult.FAIL
            notes.append("Quality evaluation recorded, but Hard Gate FAIL blocks editorial readiness.")
        elif weak_n >= 3:
            result = QualityResult.FAIL
        elif weak_n >= 1 or good_n < 4:
            result = QualityResult.NEEDS_EDIT
        else:
            result = QualityResult.PASS

        counts = {
            t: sum(1 for s in draft.statements if s.statement_type == t)
            for t in ("FACT", "INFERENCE", "HYPOTHESIS", "EXPERIMENT_PARAMETER")
        }
        meta = draft.metadata or {}
        return QualityReport(
            content_id=draft.content_id,
            content_type=draft.content_type,
            result=result,
            dimensions=dims,
            warnings=warnings,
            recommended_edits=edits,
            hard_gate_passed=hard_gate_passed,
            statement_counts=counts,
            model=str(meta.get("generator_model") or draft.generator_provider),
            prompt_version=meta.get("prompt_version"),
            notes=notes,
        )
