"""Content quality v1 tests — deterministic, zero live network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from content.ai_style import detect_ai_style_patterns
from content.generator import DraftSection, DraftStatement, StructuredDraft, get_generator
from content.golden_benchmark import compare_to_golden_style
from content.llm_generator import load_generation_prompt
from content.llm_ledger import LLMCallLedger, LedgerEntry
from content.model_benchmark import recommend_model
from content.model_escalation import default_escalation_policy
from content.quality import ContentQualityEvaluator, QualityResult
from content.style_profile import load_style_profile


def _draft(**kwargs) -> StructuredDraft:
    base = dict(
        draft_id="d1",
        content_id="insight:test",
        content_type="insight",
        title="智能柜缺货率为什么比GMV更先暴露经营问题",
        summary="缺货率与补货及时率能更早反映终端经营质量。",
        sections=[
            DraftSection(
                title="问题",
                body="柜机成交变差时，只盯GMV往往停在结果层。缺货率更能提示经营质量变化。",
                claim_ids=["c1"],
            )
        ],
        statements=[
            DraftStatement(
                text="缺货率与补货及时率更能反映智能柜终端经营质量。",
                statement_type="FACT",
                claim_ids=["c1"],
            )
        ],
        generator_provider="mock",
        metadata={"generator_model": "mock", "prompt_version": 2},
    )
    base.update(kwargs)
    if isinstance(base.get("sections"), list) and base["sections"] and isinstance(base["sections"][0], dict):
        base["sections"] = [DraftSection.from_dict(s) for s in base["sections"]]
    if isinstance(base.get("statements"), list) and base["statements"] and isinstance(base["statements"][0], dict):
        base["statements"] = [DraftStatement.from_dict(s) for s in base["statements"]]
    return StructuredDraft(**base)


def test_style_profile_loads():
    profile = load_style_profile()
    assert profile.language == "zh-CN"
    assert "专业" in profile.tone
    assert profile.ai_style_patterns


def test_prompt_v2_exists_and_version():
    p = load_generation_prompt(version=2)
    assert int(p["version"]) == 2
    assert p["model"] == "deepseek-v4-flash"
    assert "ONE SIGNAL" in p["system"] or "Daily" in p["system"]


def test_ai_style_detection_warning():
    text = "值得注意的是，不难发现智能柜正在发展。未来值得期待。"
    warnings = detect_ai_style_patterns(text)
    assert warnings
    assert all(w.code == "STYLE_PATTERN_WARNING" for w in warnings)


def test_quality_not_percent_score():
    report = ContentQualityEvaluator().evaluate(_draft(), hard_gate_passed=True)
    assert report.result in {QualityResult.PASS, QualityResult.NEEDS_EDIT, QualityResult.FAIL}
    blob = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "87.3" not in blob
    assert report.to_dict()["scoring_policy"] == "ordinal_levels_only_no_percent_score"
    assert set(report.to_dict()["dimensions"]) >= {
        "clarity",
        "structure",
        "professionalism",
        "specificity",
        "redundancy",
        "ai_style",
        "evidence_usage",
        "reader_value",
    }


def test_quality_separate_from_hard_gate_fail():
    report = ContentQualityEvaluator().evaluate(_draft(), hard_gate_passed=False)
    assert report.result is QualityResult.FAIL
    assert any("Hard Gate" in n for n in report.notes)


def test_golden_style_benchmark_no_total_score():
    diff = compare_to_golden_style(_draft())
    assert "diffs" in diff
    assert "score" not in diff
    assert diff["golden_slug"] == "smart-cabinet-five-process-metrics"


def test_escalation_disabled_by_default():
    policy = default_escalation_policy()
    assert policy.enabled is False
    flash = {"gate": "FAIL", "quality": "FAIL"}
    pro = {"gate": "PASS", "quality": "PASS"}
    # recommendation may suggest Pro, but policy remains disabled / default unchanged
    assert recommend_model(flash, pro) in {
        "PRO_RECOMMENDED_FOR_THIS_CONTENT",
        "FLASH_SUFFICIENT",
    }
    assert default_escalation_policy().enabled is False


def test_ledger_summary(tmp_path):
    ledger = LLMCallLedger(tmp_path / "ledger.jsonl")
    ledger.add(
        LedgerEntry(
            run_id=ledger.run_id,
            content_id="c1",
            provider="deepseek",
            model="deepseek-v4-flash",
            task="t",
            input_tokens=10,
            output_tokens=5,
            estimated_cost=0.01,
        )
    )
    s = ledger.summary()
    assert s["total_llm_calls"] == 1
    assert s["total_input_tokens"] == 10
    assert "Authorization" not in json.dumps(s)


def test_ci_default_remains_mock(monkeypatch):
    monkeypatch.setenv("CONTENT_GENERATOR_PROVIDER", "mock")
    monkeypatch.setenv("CONTENT_GENERATOR_ALLOW_LIVE", "0")
    assert get_generator().name == "mock"


def test_prompt_regression_fixtures_exist():
    root = Path("tests/fixtures/content_generation")
    names = sorted(p.name for p in root.iterdir() if p.is_dir())
    assert len(names) >= 10
    for name in names:
        exp = json.loads((root / name / "expected.json").read_text(encoding="utf-8"))
        assert "expected_gate" in exp
        assert exp["expected_gate"] in {"PASS", "FAIL"}


def test_ai_style_fixture_expects_warning():
    exp = json.loads(
        Path("tests/fixtures/content_generation/09_ai_style_heavy/expected.json").read_text(
            encoding="utf-8"
        )
    )
    assert exp.get("expect_style_warning") is True
    text = "值得注意的是，智能柜值得讨论。"
    assert detect_ai_style_patterns(text)


def test_editorial_style_yaml_parses():
    data = yaml.safe_load(Path("config/editorial_style.yaml").read_text(encoding="utf-8"))
    assert data["golden_benchmark"]["slug"] == "smart-cabinet-five-process-metrics"


def test_recommend_flash_sufficient_when_both_ok():
    flash = {"gate": "PASS", "quality": "PASS"}
    pro = {"gate": "PASS", "quality": "PASS"}
    assert recommend_model(flash, pro) == "FLASH_SUFFICIENT"


def test_shadow_artifacts_with_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_GENERATOR_PROVIDER", "mock")
    monkeypatch.setenv("CONTENT_GENERATOR_ALLOW_LIVE", "0")
    from content.brief import build_editorial_brief
    from content.candidates import build_candidate_from_knowledge
    from content.models import ContentType, EditorialStatus, make_content_id
    from content.shadow import build_editorial_package, run_shadow_generation
    from research.atom_store import ResearchAtomStore
    from research.claim_review import set_claim_status
    from research.intake import news_to_research_atoms
    from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
    from research.models import ClaimStatus

    atoms = news_to_research_atoms(
        {
            "title": "智能柜过程指标",
            "url": "https://example.test/shadow-mock",
            "source_name": "Test",
            "published_at": "2026-08-07T10:00:00+08:00",
            "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量。",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={"intake": "test", "source_tier": "A"},
    )
    set_claim_status(
        store,
        atoms.claims[0].id,
        ClaimStatus.VERIFIED,
        reviewer="alice",
        reason="test",
        log_path=tmp_path / "claim.jsonl",
        persist=True,
    )
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    cand = build_candidate_from_knowledge(
        [knowledge.list_active()[0]], content_type=ContentType.INSIGHT
    )
    cand.slug = "shadow-mock"
    cand.content_id = make_content_id("insight", cand.slug)
    build_editorial_brief(cand)
    out = tmp_path / "shadow"
    result = run_shadow_generation(cand, atom_store=store, out_dir=out, model="mock")
    # mock path may not be deepseek; force generator via env
    assert (out / "draft.json").exists()
    assert (out / "gate-report.json").exists()
    assert (out / "quality-report.json").exists()
    assert result["editorial_status"] == "PENDING"
    assert cand.editorial_status is EditorialStatus.PENDING
    pkg = build_editorial_package(shadow_dir=out, package_dir=tmp_path / "editorial")
    assert (Path(pkg["package_path"]) / "article.md").exists()
    assert (Path(pkg["package_path"]) / "editorial-brief.md").exists()
    assert pkg["editorial_status"] == "PENDING"


def test_budget_env_documented():
    from content.model_escalation import default_escalation_policy

    assert default_escalation_policy().enabled is False
    assert default_escalation_policy().auto_call_pro is False
