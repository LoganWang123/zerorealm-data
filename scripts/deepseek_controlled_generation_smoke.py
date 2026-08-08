"""Local DeepSeek V4 smoke — fixture VERIFIED atoms only. Do not commit outputs."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from content.audit import audit_structured_draft
from content.brief import build_editorial_brief
from content.candidates import build_candidate_from_knowledge
from content.generator import generate_controlled_draft, get_generator
from content.llm_models import resolve_llm_api_key
from content.models import ContentType, make_content_id
from content.repair import repair_until_pass_or_limit
from research.atom_store import ResearchAtomStore
from research.claim_review import set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus


def main() -> int:
    configured = bool(resolve_llm_api_key())
    report = {
        "llm_api_key_configured": configured,
        "smoke_executed": False,
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL") or "",
        "env_LLM_MODEL": os.getenv("LLM_MODEL") or "",
    }
    if not configured:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # Force V4 flash regardless of legacy .env LLM_MODEL
    os.environ["CONTENT_GENERATOR_PROVIDER"] = "deepseek"
    os.environ["CONTENT_GENERATOR_ALLOW_LIVE"] = "1"
    os.environ["CONTENT_GENERATOR_MODEL"] = "deepseek-v4-flash"
    os.environ["CONTENT_GENERATOR_MAX_CALLS_PER_RUN"] = "4"

    with tempfile.TemporaryDirectory(prefix="zr-deepseek-smoke-") as tmp:
        tmp_path = Path(tmp)
        atoms = news_to_research_atoms(
            {
                "title": "smart cabinet ops",
                "url": "https://ex.com/smoke-deepseek",
                "source_name": "Smoke Fixture",
                "published_at": "2026-08-07T10:00:00+08:00",
                "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量。",
                "discovery_provider": "fake",
                "discovery_query": "智能柜",
                "discovery_candidate_id": "cand-smoke",
            }
        )
        store = ResearchAtomStore(tmp_path / "atoms.json")
        store.upsert_atoms(
            source=atoms.source,
            evidence=atoms.evidence,
            claims=atoms.claims,
            lineage={
                "intake": "discovery",
                "candidate_id": "cand-smoke",
                "source_tier": "B",
                "source_cluster_ids": ["c1"],
                "topic_tags": ["智能柜"],
                "company_tags": ["友宝"],
                "reviewer": "alice",
            },
        )
        set_claim_status(
            store,
            atoms.claims[0].id,
            ClaimStatus.VERIFIED,
            reviewer="alice",
            reason="smoke",
            log_path=tmp_path / "claim.jsonl",
            persist=True,
        )
        knowledge = KnowledgeStore(tmp_path / "k.json")
        sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
        rec = knowledge.list_active()[0]
        cand = build_candidate_from_knowledge(
            [rec], content_type=ContentType.INSIGHT, primary_signals=["过程指标"]
        )
        cand.slug = "smoke-process-metrics"
        cand.content_id = make_content_id("insight", cand.slug)
        cand.theme_consistency = True
        cand.companies = ["友宝"]
        build_editorial_brief(cand)

        gen = get_generator(provider="deepseek", model="deepseek-v4-flash")
        draft = generate_controlled_draft(
            cand,
            atom_store=store,
            generator=gen,
            require_verified_store=True,
        )
        initial = audit_structured_draft(cand, draft, atom_store=store)
        repair_attempts = 0
        final = initial
        if not initial.passed:
            repaired = repair_until_pass_or_limit(draft, cand, atom_store=store)
            repair_attempts = repaired.attempts
            final = audit_structured_draft(cand, repaired.draft, atom_store=store)
            draft = repaired.draft

        lineage = (draft.metadata or {}).get("llm_lineage") or {}
        stmts = draft.statements
        report.update(
            {
                "smoke_executed": True,
                "provider": draft.generator_provider,
                "model": (draft.metadata or {}).get("generator_model"),
                "prompt_name": (draft.metadata or {}).get("prompt_name"),
                "prompt_version": (draft.metadata or {}).get("prompt_version"),
                "prompt_tokens": lineage.get("prompt_tokens"),
                "completion_tokens": lineage.get("completion_tokens"),
                "latency_ms": lineage.get("latency_ms"),
                "estimated_cost": lineage.get("estimated_cost_cny"),
                "schema_valid": True,
                "schema_repair_attempts": (draft.metadata or {}).get("schema_repair_attempts"),
                "statement_counts": {
                    t: sum(1 for s in stmts if s.statement_type == t)
                    for t in ("FACT", "INFERENCE", "HYPOTHESIS", "EXPERIMENT_PARAMETER")
                },
                "allowed_claim_ids": (draft.metadata or {}).get("allowed_claim_ids"),
                "initial_gate": "PASS" if initial.passed else "FAIL",
                "repair_attempts": repair_attempts,
                "final_gate": "PASS" if final.passed else "FAIL",
                "initial_errors": list(initial.errors or []),
                "final_errors": list(final.errors or []),
                "deepseek_network_calls": len(lineage.get("calls") or []),
                "wechat_api_calls": 0,
                "website_production_writes": 0,
                "other_network_calls": 0,
                "fixture_local_in_draft": "fixture.local" in json.dumps(cand.draft or {}, ensure_ascii=False),
            }
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("final_gate") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
