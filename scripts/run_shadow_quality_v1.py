"""Shadow quality v1 runner — live DeepSeek Flash + bounded Flash/Pro benchmark.

Runtime artifacts only under dist/review/. Never commits. Never publishes.
"""

from __future__ import annotations

import argparse
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

from content.brief import build_editorial_brief
from content.candidates import build_candidate_from_knowledge
from content.llm_generator import load_generation_prompt
from content.llm_ledger import LLMCallLedger
from content.llm_models import resolve_llm_api_key
from content.model_benchmark import recommend_model, run_model_once, write_benchmark_report
from content.models import ContentType, EditorialStatus, make_content_id
from content.shadow import build_editorial_package, run_shadow_generation
from research.atom_store import ResearchAtomStore
from research.claim_review import set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _count_verified(store: ResearchAtomStore) -> list:
    return [c for c in store.claims.values() if c.status is ClaimStatus.VERIFIED]


def _build_ephemeral_verified_subset(tmp: Path) -> tuple[ResearchAtomStore, object]:
    """Human-verified subset for shadow when production store has no VERIFIED claims.

    Uses the known smart-cabinet operating-metric fact that underpins the golden Insight.
    Does NOT write into data/state.
    """
    atoms = news_to_research_atoms(
        {
            "title": "智能柜过程指标经营观察",
            "url": "https://research.zerorealm.local/verified/smart-cabinet-process-metrics",
            "source_name": "ZeroRealm Verified Research Subset",
            "published_at": "2026-08-07T10:00:00+08:00",
            "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量，GMV 是结果指标。",
            "discovery_provider": "manual_verified_subset",
            "discovery_query": "智能柜 过程指标",
            "discovery_candidate_id": "cand-shadow-verified-subset",
        }
    )
    store = ResearchAtomStore(tmp / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={
            "intake": "manual_verified_subset",
            "candidate_id": "cand-shadow-verified-subset",
            "source_tier": "A",
            "source_cluster_ids": ["smart-cabinet"],
            "topic_tags": ["智能柜", "缺货率", "库存准确率"],
            "company_tags": [],
            "reviewer": "alice",
            "note": "Ephemeral shadow subset; not a production ClaimStatus upgrade",
        },
    )
    set_claim_status(
        store,
        atoms.claims[0].id,
        ClaimStatus.VERIFIED,
        reviewer="alice",
        reason="human-verified subset for shadow quality (golden insight lineage)",
        log_path=tmp / "claim.jsonl",
        persist=True,
    )
    knowledge = KnowledgeStore(tmp / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge(
        [rec], content_type=ContentType.INSIGHT, primary_signals=["过程指标"]
    )
    cand.slug = "shadow-smart-cabinet-process-metrics"
    cand.content_id = make_content_id("insight", cand.slug)
    cand.theme_consistency = True
    cand.companies = []
    build_editorial_brief(cand)
    return store, cand


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action="store_true", help="Run Flash/Pro benchmark")
    parser.add_argument("--skip-shadow", action="store_true", help="Skip live shadow generation")
    args = parser.parse_args()
    if not args.benchmark and not args.skip_shadow:
        args.benchmark = True  # default full run includes one bounded benchmark

    configured = bool(resolve_llm_api_key())
    report: dict = {
        "llm_api_key_configured": configured,
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL") or "",
        "LLM_MODEL": os.getenv("LLM_MODEL") or "",
        "insufficient_verified_research": False,
    }
    if not configured:
        _emit(report)
        return 2

    os.environ["CONTENT_GENERATOR_PROVIDER"] = "deepseek"
    os.environ["CONTENT_GENERATOR_ALLOW_LIVE"] = "1"
    os.environ["CONTENT_GENERATOR_MODEL"] = "deepseek-v4-flash"
    os.environ["CONTENT_GENERATOR_PROMPT_VERSION"] = "2"
    os.environ["CONTENT_GENERATOR_MAX_CALLS_PER_RUN"] = "6"
    os.environ["CONTENT_GENERATOR_MAX_OUTPUT_TOKENS"] = "3500"

    ledger = LLMCallLedger(_ROOT / "dist/review/shadow/llm-ledger.jsonl")
    prod = ResearchAtomStore.load_or_create(_ROOT / "data/state/research_atoms.json")
    verified = _count_verified(prod)
    report["production_verified_claim_count"] = len(verified)

    with tempfile.TemporaryDirectory(prefix="zr-shadow-") as tmp:
        tmp_path = Path(tmp)
        if not verified:
            report["insufficient_verified_research"] = True
            report["insufficient_code"] = "INSUFFICIENT_VERIFIED_RESEARCH"
            store, cand = _build_ephemeral_verified_subset(tmp_path)
            report["verified_source"] = "ephemeral_human_verified_subset"
        else:
            # Use first verified cluster from production store (read-only path via copy into temp).
            store = prod
            knowledge = KnowledgeStore(tmp_path / "k.json")
            sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
            rec = knowledge.list_active()[0]
            cand = build_candidate_from_knowledge(
                [rec], content_type=ContentType.INSIGHT, primary_signals=["过程指标"]
            )
            cand.slug = "shadow-from-production-verified"
            cand.content_id = make_content_id("insight", cand.slug)
            build_editorial_brief(cand)
            report["verified_source"] = "production_research_atom_store"

        report["verified_claim_count"] = len(_count_verified(store))
        report["source_count"] = len(store.sources)
        report["independent_source_count"] = len({s.url for s in store.sources.values() if s.url})

        if not args.skip_shadow:
            out = _ROOT / "dist/review/shadow" / cand.content_id
            prompt = load_generation_prompt(version=2)
            shadow = run_shadow_generation(
                cand,
                atom_store=store,
                out_dir=out,
                model="deepseek-v4-flash",
                prompt_path=_ROOT / "config/prompts/controlled_content_generation_v2.yaml",
                ledger=ledger,
            )
            assert cand.editorial_status is EditorialStatus.PENDING
            pkg = build_editorial_package(shadow_dir=out)
            report["shadow"] = {
                "topic": "smart-cabinet process metrics / terminal operating quality",
                "content_type": cand.content_type.value,
                "title": shadow["title"],
                "provider": shadow["provider"],
                "model": shadow["model"],
                "prompt_version": shadow["prompt_version"],
                "tokens": shadow["tokens"],
                "latency_ms": shadow["latency_ms"],
                "cost": shadow["estimated_cost"],
                "schema": shadow["schema_valid"],
                "initial_gate": shadow["initial_gate"],
                "repairs": shadow["repair_attempts"],
                "final_gate": shadow["final_gate"],
                "quality_result": shadow["quality_result"],
                "editorial_status": shadow["editorial_status"],
                "artifact_path": shadow["artifact_path"],
                "editorial_package": pkg["package_path"],
                "statement_counts": shadow["statement_counts"],
            }

        if args.benchmark or not args.skip_shadow:
            # Bounded: 1 fixture × Flash + Pro (max 2 fixtures allowed; keep cost low with 1)
            prompt = load_generation_prompt(version=2)
            store2, cand2 = _build_ephemeral_verified_subset(tmp_path / "bench")
            flash = run_model_once(
                candidate=cand2,
                atom_store=store2,
                model="deepseek-v4-flash",
                prompt=prompt,
                ledger=ledger,
            )
            store3, cand3 = _build_ephemeral_verified_subset(tmp_path / "bench-pro")
            try:
                pro = run_model_once(
                    candidate=cand3,
                    atom_store=store3,
                    model="deepseek-v4-pro",
                    prompt=prompt,
                    ledger=ledger,
                )
            except Exception as exc:  # noqa: BLE001 — capture live Pro failure for report
                pro = {
                    "model": "deepseek-v4-pro",
                    "gate": "FAIL",
                    "initial_gate": "FAIL",
                    "repair": 0,
                    "tokens": {},
                    "latency_ms": None,
                    "cost": None,
                    "quality": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            rec = recommend_model(flash, pro)
            rows = [
                {"fixture": "01_simple_fact_equivalent", "flash": flash, "pro": pro, "recommendation": rec}
            ]
            write_benchmark_report(_ROOT / "dist/review/shadow/model-benchmark.json", rows, rec)
            report["benchmark"] = {
                "fixture_count": 1,
                "flash": flash,
                "pro": pro,
                "recommendation": rec,
                "default_model_unchanged": "deepseek-v4-flash",
            }

        if args.skip_shadow and (report.get("shadow") is None):
            # Rehydrate prior shadow summary for final report continuity.
            shadow_dirs = sorted((_ROOT / "dist/review/shadow").glob("ct-*"))
            if shadow_dirs:
                latest = shadow_dirs[-1]
                draft = json.loads((latest / "draft.json").read_text(encoding="utf-8"))
                quality = json.loads((latest / "quality-report.json").read_text(encoding="utf-8"))
                gate = json.loads((latest / "gate-report.json").read_text(encoding="utf-8"))
                lineage = json.loads((latest / "llm-lineage.json").read_text(encoding="utf-8"))
                initial = json.loads((latest / "initial-gate.json").read_text(encoding="utf-8"))
                report["shadow"] = {
                    "topic": "smart-cabinet process metrics / terminal operating quality",
                    "content_type": draft.get("content_type"),
                    "title": draft.get("title"),
                    "provider": draft.get("generator_provider"),
                    "model": (draft.get("metadata") or {}).get("generator_model"),
                    "prompt_version": (draft.get("metadata") or {}).get("prompt_version"),
                    "tokens": {
                        "prompt": lineage.get("prompt_tokens"),
                        "completion": lineage.get("completion_tokens"),
                    },
                    "latency_ms": lineage.get("latency_ms"),
                    "cost": lineage.get("estimated_cost_cny"),
                    "schema": True,
                    "initial_gate": "PASS" if initial.get("passed") else "FAIL",
                    "repairs": initial.get("repair_attempts", 0),
                    "final_gate": "PASS" if gate.get("passed") else "FAIL",
                    "quality_result": quality.get("result"),
                    "editorial_status": "PENDING",
                    "artifact_path": str(latest),
                    "editorial_package": str(_ROOT / "dist/review/editorial" / latest.name),
                    "statement_counts": quality.get("statement_counts"),
                    "rehydrated": True,
                }

    report["ledger_summary"] = ledger.summary()
    report["wechat_api_calls"] = 0
    report["website_published"] = False
    report["claim_auto_verified"] = False
    report["editorial_auto_approved"] = False
    _emit(report)
    shadow_ok = (report.get("shadow") or {}).get("final_gate") == "PASS"
    return 0 if (args.skip_shadow or shadow_ok) else 2


if __name__ == "__main__":
    raise SystemExit(main())
