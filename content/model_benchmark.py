"""Flash vs Pro quality benchmark helpers (bounded calls)."""

from __future__ import annotations

import json
from pathlib import Path

from content.audit import audit_structured_draft
from content.generator import generate_controlled_draft, get_generator
from content.llm_generator import LLMContentGenerator, load_generation_prompt, prompt_hash
from content.llm_ledger import LLMCallLedger, LedgerEntry
from content.model_escalation import default_escalation_policy
from content.models import ContentCandidate
from content.quality import ContentQualityEvaluator
from content.repair import repair_until_pass_or_limit
from research.atom_store import ResearchAtomStore


def run_model_once(
    *,
    candidate: ContentCandidate,
    atom_store: ResearchAtomStore,
    model: str,
    prompt: dict,
    ledger: LLMCallLedger | None = None,
) -> dict:
    gen = get_generator(provider="deepseek", model=model)
    if isinstance(gen, LLMContentGenerator):
        gen.prompt = prompt
        gen.model = model
    draft = generate_controlled_draft(
        candidate,
        atom_store=atom_store,
        generator=gen,
        require_verified_store=True,
    )
    initial = audit_structured_draft(candidate, draft, atom_store=atom_store)
    repairs = 0
    final = initial
    if not initial.passed:
        repaired = repair_until_pass_or_limit(draft, candidate, atom_store=atom_store)
        repairs = repaired.attempts
        draft = repaired.draft
        final = audit_structured_draft(candidate, draft, atom_store=atom_store)
    quality = ContentQualityEvaluator().evaluate(
        draft, candidate=candidate, hard_gate_passed=bool(final.passed)
    )
    lineage = (draft.metadata or {}).get("llm_lineage") or {}
    if ledger is not None:
        ledger.add(
            LedgerEntry(
                run_id=ledger.run_id,
                content_id=draft.content_id,
                provider="deepseek",
                model=model,
                task="model_benchmark",
                prompt_version=int(prompt.get("version") or 0),
                prompt_hash=prompt_hash(prompt),
                input_tokens=int(lineage.get("prompt_tokens") or 0),
                output_tokens=int(lineage.get("completion_tokens") or 0),
                latency_ms=int(lineage.get("latency_ms") or 0),
                estimated_cost=float(lineage.get("estimated_cost_cny") or 0),
                schema_result="PASS",
                gate_result="PASS" if final.passed else "FAIL",
            )
        )
    return {
        "model": model,
        "gate": "PASS" if final.passed else "FAIL",
        "initial_gate": "PASS" if initial.passed else "FAIL",
        "repair": repairs,
        "tokens": {
            "prompt": lineage.get("prompt_tokens"),
            "completion": lineage.get("completion_tokens"),
        },
        "latency_ms": lineage.get("latency_ms"),
        "cost": lineage.get("estimated_cost_cny"),
        "quality": quality.result.value,
        "dimensions": {d.name: d.level.value for d in quality.dimensions},
        "title": draft.title,
    }


def recommend_model(flash: dict, pro: dict) -> str:
    """Never changes global default. Advisory only."""
    policy = default_escalation_policy()
    assert policy.enabled is False
    if flash.get("gate") == "PASS" and flash.get("quality") in {"PASS", "NEEDS_EDIT"}:
        if pro.get("quality") == "PASS" and flash.get("quality") == "FAIL":
            return "PRO_RECOMMENDED_FOR_THIS_CONTENT"
        if flash.get("quality") == "NEEDS_EDIT" and pro.get("quality") == "PASS":
            # Only recommend if Pro clearly improves key outcome
            return "PRO_RECOMMENDED_FOR_THIS_CONTENT"
        return "FLASH_SUFFICIENT"
    if flash.get("gate") != "PASS" and pro.get("gate") == "PASS":
        return "PRO_RECOMMENDED_FOR_THIS_CONTENT"
    return "FLASH_SUFFICIENT"


def write_benchmark_report(path: Path, rows: list[dict], recommendation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rows": rows, "recommendation": recommendation, "default_model_unchanged": "deepseek-v4-flash"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
