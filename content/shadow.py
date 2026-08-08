"""Shadow production + editorial package builders (runtime artifacts only)."""

from __future__ import annotations

import json
from pathlib import Path

from content.audit import audit_structured_draft
from content.generator import StructuredDraft, generate_controlled_draft, get_generator
from content.golden_benchmark import compare_to_golden_style
from content.llm_generator import load_generation_prompt, prompt_hash
from content.llm_ledger import LLMCallLedger, LedgerEntry
from content.models import ContentCandidate, EditorialStatus
from content.quality import ContentQualityEvaluator
from content.repair import repair_until_pass_or_limit
from research.atom_store import ResearchAtomStore
from utils.helpers import now_iso


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def draft_to_markdown(draft: StructuredDraft) -> str:
    lines = [f"# {draft.title}", "", draft.summary or "", ""]
    for sec in draft.sections:
        lines.append(f"## {sec.title}")
        lines.append("")
        lines.append(sec.body)
        if sec.claim_ids:
            lines.append("")
            lines.append("Claims: " + ", ".join(sec.claim_ids))
        lines.append("")
    lines.append("## Statements")
    lines.append("")
    for s in draft.statements:
        lines.append(f"- [{s.statement_type}] {s.text}")
        if s.claim_ids:
            lines.append(f"  - claim_ids: {', '.join(s.claim_ids)}")
    return "\n".join(lines).rstrip() + "\n"


def run_shadow_generation(
    candidate: ContentCandidate,
    *,
    atom_store: ResearchAtomStore,
    out_dir: str | Path,
    model: str = "deepseek-v4-flash",
    prompt_path: Path | None = None,
    ledger: LLMCallLedger | None = None,
) -> dict:
    """Live DeepSeek shadow generate → gate → quality. Never publishes."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prompt = load_generation_prompt(prompt_path) if prompt_path else load_generation_prompt(
        Path(__file__).resolve().parent.parent / "config" / "prompts" / "controlled_content_generation_v2.yaml"
    )
    # Respect CONTENT_GENERATOR_PROVIDER (CI/default=mock; live shadow sets deepseek).
    gen = get_generator(model=model)
    from content.llm_generator import LLMContentGenerator

    if isinstance(gen, LLMContentGenerator):
        gen.prompt = prompt
        gen.model = model

    draft = generate_controlled_draft(
        candidate,
        atom_store=atom_store,
        generator=gen,
        require_verified_store=gen.name != "mock",
    )
    initial = audit_structured_draft(candidate, draft, atom_store=atom_store)
    repair_attempts = 0
    final_audit = initial
    if not initial.passed:
        repaired = repair_until_pass_or_limit(draft, candidate, atom_store=atom_store)
        repair_attempts = repaired.attempts
        draft = repaired.draft
        final_audit = audit_structured_draft(candidate, draft, atom_store=atom_store)

    quality = ContentQualityEvaluator().evaluate(
        draft,
        candidate=candidate,
        hard_gate_passed=bool(final_audit.passed),
    )
    # Editorial always pending
    candidate.editorial_status = EditorialStatus.PENDING

    lineage = (draft.metadata or {}).get("llm_lineage") or {}
    if ledger is not None:
        ledger.add(
            LedgerEntry(
                run_id=ledger.run_id,
                content_id=draft.content_id,
                provider=str(draft.generator_provider),
                model=str((draft.metadata or {}).get("generator_model") or model),
                task="shadow_controlled_generation",
                prompt_version=int((draft.metadata or {}).get("prompt_version") or prompt.get("version") or 2),
                prompt_hash=str((draft.metadata or {}).get("prompt_hash") or prompt_hash(prompt)),
                input_tokens=int(lineage.get("prompt_tokens") or 0),
                output_tokens=int(lineage.get("completion_tokens") or 0),
                latency_ms=int(lineage.get("latency_ms") or 0),
                estimated_cost=float(lineage.get("estimated_cost_cny") or 0),
                schema_result="PASS",
                gate_result="PASS" if final_audit.passed else "FAIL",
            )
        )

    style_diff = compare_to_golden_style(draft)
    _write_json(out / "draft.json", draft.to_dict())
    _write_text(out / "draft.md", draft_to_markdown(draft))
    _write_json(out / "allowed-facts.json", (candidate.metadata or {}).get("allowed_facts") or {})
    _write_json(out / "gate-report.json", final_audit.to_dict())
    _write_json(out / "quality-report.json", quality.to_dict())
    _write_json(out / "llm-lineage.json", lineage)
    _write_json(
        out / "editorial-brief.json",
        {
            "editorial_status": "PENDING",
            "hard_gate": "PASS" if final_audit.passed else "FAIL",
            "quality": quality.result.value,
            "generated_at": now_iso(),
            "auto_approved": False,
        },
    )
    _write_json(out / "style-benchmark.json", style_diff)
    _write_json(
        out / "initial-gate.json",
        {
            "passed": initial.passed,
            "errors": list(initial.errors or []),
            "repair_attempts": repair_attempts,
        },
    )

    return {
        "artifact_path": str(out),
        "content_id": draft.content_id,
        "title": draft.title,
        "provider": draft.generator_provider,
        "model": (draft.metadata or {}).get("generator_model"),
        "prompt_version": (draft.metadata or {}).get("prompt_version") or prompt.get("version"),
        "schema_valid": True,
        "initial_gate": "PASS" if initial.passed else "FAIL",
        "repair_attempts": repair_attempts,
        "final_gate": "PASS" if final_audit.passed else "FAIL",
        "quality_result": quality.result.value,
        "editorial_status": "PENDING",
        "tokens": {
            "prompt": lineage.get("prompt_tokens"),
            "completion": lineage.get("completion_tokens"),
        },
        "latency_ms": lineage.get("latency_ms"),
        "estimated_cost": lineage.get("estimated_cost_cny"),
        "statement_counts": quality.statement_counts,
        "draft": draft,
        "quality": quality,
        "audit": final_audit,
    }


def build_editorial_package(
    *,
    shadow_dir: str | Path,
    atom_store: ResearchAtomStore | None = None,
    package_dir: str | Path | None = None,
) -> dict:
    shadow = Path(shadow_dir)
    draft = StructuredDraft.from_dict(json.loads((shadow / "draft.json").read_text(encoding="utf-8")))
    gate = json.loads((shadow / "gate-report.json").read_text(encoding="utf-8"))
    quality = json.loads((shadow / "quality-report.json").read_text(encoding="utf-8"))
    lineage = json.loads((shadow / "llm-lineage.json").read_text(encoding="utf-8"))
    allowed = json.loads((shadow / "allowed-facts.json").read_text(encoding="utf-8"))
    style = json.loads((shadow / "style-benchmark.json").read_text(encoding="utf-8"))
    out = Path(package_dir or f"dist/review/editorial/{draft.content_id}")
    out.mkdir(parents=True, exist_ok=True)

    _write_text(out / "article.md", draft_to_markdown(draft))

    claim_lines = ["# Claim Map", ""]
    for s in draft.statements:
        claim_lines.append(f"## [{s.statement_type}] {s.text}")
        claim_lines.append(f"- claim_ids: {', '.join(s.claim_ids) or '(none)'}")
        claim_lines.append("")
    _write_text(out / "claim-map.md", "\n".join(claim_lines))

    source_lines = ["# Source Map", ""]
    for src in allowed.get("allowed_sources") or []:
        source_lines.append(f"- `{src.get('source_document_id')}` {src.get('title')}")
        source_lines.append(f"  - URL: {src.get('url')}")
    _write_text(out / "source-map.md", "\n".join(source_lines) + "\n")

    brief = [
        "# Editorial Brief",
        "",
        f"- content_id: `{draft.content_id}`",
        f"- type: `{draft.content_type}`",
        f"- title: {draft.title}",
        f"- Hard Gate: **{('PASS' if gate.get('passed') else 'FAIL')}**",
        f"- Quality: **{quality.get('result')}**",
        "- Editorial status: **PENDING** (not auto-approved)",
        f"- model: `{quality.get('model')}`",
        f"- prompt_version: `{quality.get('prompt_version')}`",
        "",
        "## Recommended edits",
        "",
    ]
    for e in quality.get("recommended_edits") or []:
        brief.append(f"- {e}")
    if quality.get("warnings"):
        brief.append("")
        brief.append("## Warnings")
        brief.append("")
        for w in quality["warnings"]:
            brief.append(f"- `{w.get('code')}` {w.get('pattern')} ×{w.get('count')}")
    _write_text(out / "editorial-brief.md", "\n".join(brief) + "\n")

    qmd = ["# Quality Report", "", f"Result: **{quality.get('result')}**", ""]
    for name, row in (quality.get("dimensions") or {}).items():
        qmd.append(f"- {name}: {row.get('level')} — {row.get('reason')}")
    _write_text(out / "quality-report.md", "\n".join(qmd) + "\n")

    _write_json(out / "gate-report.json", gate)
    _write_json(out / "llm-usage.json", lineage)
    diff_lines = ["# Diff vs Golden Style Benchmark", ""]
    for d in style.get("diffs") or []:
        diff_lines.append(f"- {d['dimension']}: {d['assessment']} — {d['note']}")
    _write_text(out / "diff-vs-style-benchmark.md", "\n".join(diff_lines) + "\n")

    return {"package_path": str(out), "editorial_status": "PENDING", "content_id": draft.content_id}
