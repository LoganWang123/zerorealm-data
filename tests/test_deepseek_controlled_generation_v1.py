"""DeepSeek / LLM controlled generation tests — fake LLMClient only (zero network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from content.allowed_facts import AllowedFactsError, build_allowed_facts
from content.audit import audit_structured_draft
from content.brief import build_editorial_brief
from content.candidates import build_candidate_from_knowledge
from content.generator import generate_controlled_draft, get_generator
from content.llm_generator import GenerationError, LLMContentGenerator, validate_structured_payload
from content.llm_models import LLMConfigError, assert_supported_model, resolve_llm_api_key
from content.models import ContentType, make_content_id
from content.repair import repair_until_pass_or_limit
from research.atom_store import ResearchAtomStore
from research.claim_review import set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus


class FakeLLMResponse:
    def __init__(self, content: str, model: str = "deepseek-v4-flash"):
        self.content = content
        self.model = model
        self.prompt_tokens = 100
        self.completion_tokens = 50
        self.latency_ms = 12
        self.task = "controlled_content_generation"
        self.prompt_name = "controlled_content_generation"
        self.prompt_version = 1

    def lineage(self) -> dict:
        return {
            "operator": "model",
            "model": self.model,
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_cny": 0.0001,
        }


class FakeLLMClient:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise RuntimeError("no fake responses left")
        return FakeLLMResponse(self.responses.pop(0), model=kwargs.get("model") or "deepseek-v4-flash")


def _verified_fixture(tmp_path: Path, monkeypatch, *, experiment: bool = False):
    monkeypatch.chdir(tmp_path)
    atoms = news_to_research_atoms(
        {
            "title": "t",
            "url": "https://ex.com/deepseek-gen",
            "source_name": "Fixture Press",
            "published_at": "2026-08-07T10:00:00+08:00",
            "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量。",
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": "cand-ds",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={
            "intake": "discovery",
            "candidate_id": "cand-ds",
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
        reason="ok",
        log_path=tmp_path / "claim.jsonl",
        persist=True,
    )
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge(
        [rec], content_type=ContentType.INSIGHT, primary_signals=["过程指标"]
    )
    cand.slug = "smart-cabinet-five-process-metrics"
    cand.content_id = make_content_id("insight", cand.slug)
    cand.theme_consistency = True
    cand.companies = ["友宝"]
    if experiment:
        from content.models import StatementKind, ContentStatement

        cand.statements.append(
            ContentStatement(
                kind=StatementKind.EXPERIMENT_PARAMETER,
                text="建议用 10 台柜观察 7 天。",
                claim_ids=[],
                numeric_kind="EXPERIMENT_PARAMETER",
                labeled_experiment=True,
            )
        )
    build_editorial_brief(cand)
    return cand, store


def _valid_payload(claim_id: str, *, experiment: bool = False) -> dict:
    statements = [
        {
            "text": "缺货率与补货及时率更能反映智能柜终端经营质量。",
            "statement_type": "FACT",
            "claim_ids": [claim_id],
            "supporting_claim_ids": [],
            "numeric_kind": None,
            "formula": "",
            "inputs": [],
            "parameter_basis": "",
            "zerorealm_suggested": False,
            "industry_standard": False,
            "pending_verification": False,
        }
    ]
    if experiment:
        statements.append(
            {
                "text": "建议用 10 台柜观察 7 天。",
                "statement_type": "EXPERIMENT_PARAMETER",
                "claim_ids": [],
                "supporting_claim_ids": [],
                "numeric_kind": "EXPERIMENT_PARAMETER",
                "formula": "",
                "inputs": ["10台", "7天"],
                "parameter_basis": "zerorealm_suggested",
                "zerorealm_suggested": True,
                "industry_standard": False,
                "pending_verification": False,
            }
        )
    return {
        "title": "智能柜过程指标",
        "summary": "盯过程指标而非只盯结果。",
        "sections": [{"title": "过程指标", "body": statements[0]["text"], "claim_ids": [claim_id]}],
        "statements": statements,
    }


def test_mock_default_provider(monkeypatch):
    monkeypatch.delenv("CONTENT_GENERATOR_PROVIDER", raising=False)
    gen = get_generator()
    assert gen.name == "mock"


def test_unknown_provider_fails(monkeypatch):
    with pytest.raises(GenerationError) as exc:
        get_generator(provider="weird-vendor")
    assert exc.value.code == "UNKNOWN_CONTENT_GENERATOR_PROVIDER"


def test_deepseek_without_allow_live_fails(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    env = {
        "CONTENT_GENERATOR_ALLOW_LIVE": "0",
        "LLM_API_KEY": "sk-test",
        "CONTENT_GENERATOR_MODEL": "deepseek-v4-flash",
    }
    gen = LLMContentGenerator(provider="deepseek", client=FakeLLMClient(["{}"]), env=env)
    ctx = build_allowed_facts(cand, atom_store=store, require_verified_store=True)
    with pytest.raises(GenerationError) as exc:
        gen.generate(ctx, candidate=cand)
    assert exc.value.code == "LIVE_GENERATOR_DISABLED"


def test_deepseek_without_api_key_fails(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    env = {
        "CONTENT_GENERATOR_ALLOW_LIVE": "1",
        "CONTENT_GENERATOR_MODEL": "deepseek-v4-flash",
    }
    gen = LLMContentGenerator(provider="deepseek", env=env)
    ctx = build_allowed_facts(cand, atom_store=store, require_verified_store=True)
    with pytest.raises(GenerationError) as exc:
        gen.generate(ctx, candidate=cand)
    assert exc.value.code == "LLM_API_KEY_MISSING"


def test_live_requires_atom_store(tmp_path, monkeypatch):
    cand, _ = _verified_fixture(tmp_path, monkeypatch)
    with pytest.raises(AllowedFactsError) as exc:
        build_allowed_facts(cand, atom_store=None, require_verified_store=True)
    assert exc.value.code == "LIVE_GENERATOR_REQUIRES_VERIFIED_ATOM_STORE"


def test_legacy_models_fail_fast():
    with pytest.raises(LLMConfigError) as e1:
        assert_supported_model("deepseek-chat")
    assert e1.value.code == "DEEPSEEK_LEGACY_MODEL"
    with pytest.raises(LLMConfigError) as e2:
        assert_supported_model("deepseek-reasoner")
    assert e2.value.code == "DEEPSEEK_LEGACY_MODEL"


def test_api_key_fallback_order():
    assert resolve_llm_api_key({"LLM_API_KEY": "a", "DEEPSEEK_API_KEY": "b"}) == "a"
    assert resolve_llm_api_key({"DEEPSEEK_API_KEY": "b"}) == "b"


def test_fake_deepseek_generates_and_passes_gate(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    claim_id = cand.claim_ids[0]
    payload = _valid_payload(claim_id)
    client = FakeLLMClient([json.dumps(payload, ensure_ascii=False)])
    env = {
        "CONTENT_GENERATOR_ALLOW_LIVE": "1",
        "LLM_API_KEY": "sk-test",
        "CONTENT_GENERATOR_MODEL": "deepseek-v4-flash",
    }
    gen = LLMContentGenerator(provider="deepseek", client=client, env=env)
    draft = generate_controlled_draft(
        cand,
        atom_store=store,
        generator=gen,
        require_verified_store=True,
    )
    assert draft.generator_provider == "deepseek"
    assert draft.metadata["generator_model"] == "deepseek-v4-flash"
    assert draft.metadata["prompt_hash"]
    assert draft.metadata["llm_lineage"]["prompt_tokens"] == 100
    assert "fixture.local" not in json.dumps(cand.draft, ensure_ascii=False)
    assert cand.draft["sections"][0]["source_url"].startswith("https://ex.com/")
    audit = audit_structured_draft(cand, draft, atom_store=store)
    assert audit.passed is True
    assert client.calls[0].get("response_format") == {"type": "json_object"}
    assert gen.name != "mock"


def test_schema_repair_once_then_ok(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    claim_id = cand.claim_ids[0]
    bad = {"title": "x", "summary": "y", "sections": [], "statements": [{"text": "t", "statement_type": "NOPE"}]}
    good = _valid_payload(claim_id)
    client = FakeLLMClient([json.dumps(bad), json.dumps(good, ensure_ascii=False)])
    env = {"CONTENT_GENERATOR_ALLOW_LIVE": "1", "LLM_API_KEY": "sk-test"}
    gen = LLMContentGenerator(provider="deepseek", client=client, env=env)
    draft = generate_controlled_draft(cand, atom_store=store, generator=gen, require_verified_store=True)
    assert draft.metadata["schema_repair_attempts"] == 1
    assert len(client.calls) == 2


def test_schema_repair_exhausted(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    bad = {"title": "x", "summary": "y", "sections": [], "statements": [{"text": "t", "statement_type": "NOPE"}]}
    client = FakeLLMClient([json.dumps(bad), json.dumps(bad)])
    env = {"CONTENT_GENERATOR_ALLOW_LIVE": "1", "LLM_API_KEY": "sk-test"}
    gen = LLMContentGenerator(provider="deepseek", client=client, env=env)
    with pytest.raises(GenerationError) as exc:
        generate_controlled_draft(cand, atom_store=store, generator=gen, require_verified_store=True)
    assert exc.value.code == "GENERATOR_SCHEMA_INVALID"


def test_hallucination_hard_fail_then_repair(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    claim_id = cand.claim_ids[0]
    bad = _valid_payload(claim_id)
    bad["statements"].append(
        {
            "text": "星巴克智能柜试点证明无人零售全面爆发。",
            "statement_type": "FACT",
            "claim_ids": [claim_id],
            "supporting_claim_ids": [],
            "numeric_kind": None,
            "formula": "",
            "inputs": [],
            "parameter_basis": "",
            "zerorealm_suggested": False,
            "industry_standard": False,
            "pending_verification": False,
        }
    )
    client = FakeLLMClient([json.dumps(bad, ensure_ascii=False)])
    env = {"CONTENT_GENERATOR_ALLOW_LIVE": "1", "LLM_API_KEY": "sk-test"}
    gen = LLMContentGenerator(provider="deepseek", client=client, env=env)
    draft = generate_controlled_draft(cand, atom_store=store, generator=gen, require_verified_store=True)
    audit = audit_structured_draft(cand, draft, atom_store=store)
    assert audit.passed is False
    repaired = repair_until_pass_or_limit(draft, cand, atom_store=store)
    assert repaired.attempts >= 1
    assert not audit.passed


def test_experiment_parameter_fixture(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch, experiment=True)
    claim_id = cand.claim_ids[0]
    payload = _valid_payload(claim_id, experiment=True)
    client = FakeLLMClient([json.dumps(payload, ensure_ascii=False)])
    env = {"CONTENT_GENERATOR_ALLOW_LIVE": "1", "LLM_API_KEY": "sk-test"}
    gen = LLMContentGenerator(provider="deepseek", client=client, env=env)
    draft = generate_controlled_draft(cand, atom_store=store, generator=gen, require_verified_store=True)
    exp = [s for s in draft.statements if s.statement_type == "EXPERIMENT_PARAMETER"]
    assert exp
    assert exp[0].zerorealm_suggested is True
    assert exp[0].industry_standard is False


def test_budget_max_calls(tmp_path, monkeypatch):
    cand, store = _verified_fixture(tmp_path, monkeypatch)
    claim_id = cand.claim_ids[0]
    payload = json.dumps(_valid_payload(claim_id), ensure_ascii=False)
    # Force schema repair to consume 2 calls while budget=1
    bad = json.dumps(
        {"title": "x", "summary": "y", "sections": [], "statements": [{"text": "t", "statement_type": "NOPE"}]}
    )
    client = FakeLLMClient([bad, payload])
    env = {
        "CONTENT_GENERATOR_ALLOW_LIVE": "1",
        "LLM_API_KEY": "sk-test",
        "CONTENT_GENERATOR_MAX_CALLS_PER_RUN": "1",
    }
    gen = LLMContentGenerator(provider="deepseek", client=client, env=env)
    with pytest.raises(GenerationError) as exc:
        generate_controlled_draft(cand, atom_store=store, generator=gen, require_verified_store=True)
    assert exc.value.code == "LLM_GENERATION_BUDGET_EXCEEDED"


def test_ci_default_zero_network(monkeypatch):
    monkeypatch.setenv("CONTENT_GENERATOR_PROVIDER", "mock")
    monkeypatch.delenv("CONTENT_GENERATOR_ALLOW_LIVE", raising=False)
    gen = get_generator()
    assert gen.name == "mock"


def test_validate_statement_enum():
    with pytest.raises(GenerationError):
        validate_structured_payload(
            {
                "title": "t",
                "summary": "s",
                "sections": [],
                "statements": [{"text": "x", "statement_type": "RUMOR"}],
            }
        )
