"""Quality Scoring — rule-based + LLM-assisted signal quality assessment.

Aligned with Execution Architecture §1.2 (Understand Context):
- quality_score: 0-100
- Dimensions: Source Credibility / Content Completeness / Freshness / Relevance

Rule-based scoring runs always (zero cost).
LLM scoring is optional (call ``score_item_llm`` explicitly).
"""

import os
from dataclasses import dataclass, field
from datetime import datetime

import yaml

from crawlers.base import RawItem
from utils.helpers import CST
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# Default thresholds (overridable via settings.yaml → quality section)
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "pass": 70,       # ≥70: eligible for knowledge base / daily report
    "review": 50,     # 50-69: borderline, keep but flag
    "reject": 0,      # <50: low quality, exclude from report
}

# Dimension weights (must sum to 1.0)
WEIGHTS = {
    "source": 0.20,
    "completeness": 0.25,
    "freshness": 0.15,
    "relevance": 0.40,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Single scoring dimension."""

    name: str
    score: int        # 0-100
    weight: float
    detail: str = ""


@dataclass
class QualityResult:
    """Aggregated quality assessment."""

    total: int                              # 0-100
    dimensions: list[DimensionScore] = field(default_factory=list)
    method: str = "rule"                    # "rule" | "llm" | "hybrid"
    reason: str = ""

    @property
    def passes(self) -> bool:
        return self.total >= DEFAULT_THRESHOLDS["pass"]

    def to_dict(self) -> dict:
        return {
            "quality_score": self.total,
            "quality_method": self.method,
            "quality_reason": self.reason,
            "quality_dimensions": {
                d.name: {"score": d.score, "weight": d.weight}
                for d in self.dimensions
            },
        }


# ---------------------------------------------------------------------------
# Rule-based scoring
# ---------------------------------------------------------------------------


def score_item_rule(item: RawItem) -> QualityResult:
    """Score a signal using rules only (zero LLM cost).

    Dimensions
    ----------
    source (20%):
        Source credibility from ``item.metadata["score"]``.
    completeness (25%):
        Has URL / summary / content / reasonable title length.
    freshness (15%):
        Hours since publication (≤24 h → 100, ≥168 h → 0).
    relevance (40%):
        Boost score from keyword matching (``item.metadata["boost_score"]``).
    """
    dims: list[DimensionScore] = []

    # --- Source credibility ---
    source_score = int(item.metadata.get("score", 50))
    dims.append(DimensionScore("source", source_score, WEIGHTS["source"]))

    # --- Content completeness ---
    comp = 0
    if item.url:
        comp += 20
    if item.summary and len(item.summary.strip()) > 20:
        comp += 30
    if item.content_text and len(item.content_text.strip()) > 100:
        comp += 30
    elif item.content_html and len(item.content_html.strip()) > 100:
        comp += 20
    if item.title and len(item.title.strip()) > 10:
        comp += 20
    comp = min(comp, 100)
    dims.append(DimensionScore("completeness", comp, WEIGHTS["completeness"]))

    # --- Freshness ---
    fresh = _freshness_score(item.published_at)
    dims.append(DimensionScore("freshness", fresh, WEIGHTS["freshness"]))

    # --- Relevance (boost) ---
    boost = int(item.metadata.get("boost_score", 0))
    relevance = min(boost * 5, 100)   # boost 20 → 100
    dims.append(DimensionScore("relevance", relevance, WEIGHTS["relevance"]))

    total = round(sum(d.score * d.weight for d in dims))
    total = max(0, min(100, total))

    return QualityResult(total=total, dimensions=dims, method="rule")


def _freshness_score(published_at: str) -> int:
    """≤24 h → 100, linear decay to 0 at 168 h (7 days)."""
    if not published_at:
        return 50  # unknown → neutral
    try:
        from dateutil import parser as date_parser

        pub = date_parser.parse(published_at)
        now = datetime.now(CST)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=CST)
        hours = (now - pub).total_seconds() / 3600
        if hours <= 24:
            return 100
        if hours >= 168:
            return 0
        return round(100 - (hours - 24) / 144 * 100)
    except Exception:
        return 50


# ---------------------------------------------------------------------------
# LLM-assisted scoring (optional)
# ---------------------------------------------------------------------------


def score_item_llm(item: RawItem, llm_client=None) -> QualityResult | None:
    """Score using LLM. Returns ``None`` when client is unavailable."""
    if llm_client is None:
        return None

    logger = get_logger()

    try:
        from ai_runtime.prompt_registry import PromptRegistry

        registry = PromptRegistry()
        tpl = registry.get("quality_score")
        if tpl is None:
            logger.warning("[quality] Prompt 'quality_score' not found, skip LLM scoring")
            return None

        system, user = tpl.render(
            source_name=item.source,
            source_score=item.metadata.get("score", 50),
            title=item.title,
            summary=(item.summary or "")[:300],
            content=(item.content_text or "")[:500],
        )

        resp = llm_client.chat(
            task="quality_score",
            system=system,
            user=user,
            model=tpl.model,
            temperature=tpl.temperature,
            max_tokens=tpl.max_tokens,
            prompt_name="quality_score",
            prompt_version=tpl.version,
        )

        parsed = _parse_llm_score(resp.content)
        if parsed is not None:
            return QualityResult(
                total=parsed,
                method="llm",
                reason=resp.content.strip()[:200],
            )
    except Exception as e:
        logger.warning("[quality] LLM scoring failed: %s", e)

    return None


def _parse_llm_score(content: str) -> int | None:
    """Extract ``score`` from LLM YAML output."""
    try:
        text = content
        if "```yaml" in text:
            text = text.split("```yaml")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        data = yaml.safe_load(text.strip())
        score = data.get("score")
        if isinstance(score, (int, float)) and 0 <= score <= 100:
            return int(score)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Hybrid scoring
# ---------------------------------------------------------------------------


def score_item(item: RawItem, llm_client=None) -> QualityResult:
    """Hybrid: rule first, LLM refines when available.

    Final score = 60% rule + 40% LLM (when LLM succeeds).
    """
    rule_result = score_item_rule(item)

    if llm_client is None:
        return rule_result

    llm_result = score_item_llm(item, llm_client)
    if llm_result is None:
        return rule_result

    hybrid = round(rule_result.total * 0.6 + llm_result.total * 0.4)
    hybrid = max(0, min(100, hybrid))

    return QualityResult(
        total=hybrid,
        dimensions=rule_result.dimensions,
        method="hybrid",
        reason=llm_result.reason,
    )


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------


def apply_quality(
    items: list[RawItem],
    llm_client=None,
    threshold: int | None = None,
) -> list[RawItem]:
    """Score all items, attach ``quality_*`` to metadata, sort descending.

    Parameters
    ----------
    llm_client:
        Optional ``LLMClient`` for hybrid scoring.
    threshold:
        When set, items below this score are **excluded** from the result.
    """
    logger = get_logger()

    for item in items:
        result = score_item(item, llm_client)
        item.metadata.update(result.to_dict())

    items.sort(key=lambda x: x.metadata.get("quality_score", 0), reverse=True)

    passed = sum(1 for i in items if i.metadata.get("quality_score", 0) >= DEFAULT_THRESHOLDS["pass"])
    logger.info(
        "[quality] Scored %d items: %d passed (>=%d)",
        len(items),
        passed,
        DEFAULT_THRESHOLDS["pass"],
    )

    if threshold is not None:
        before = len(items)
        items = [i for i in items if i.metadata.get("quality_score", 0) >= threshold]
        logger.info("[quality] Filtered: %d → %d (threshold=%d)", before, len(items), threshold)

    return items
