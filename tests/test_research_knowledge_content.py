"""Research Knowledge → Content Candidate → Gate → Editorial → Package tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from content.brief import build_editorial_brief, build_internal_draft
from content.candidates import build_candidate_from_knowledge
from content.editorial_review import set_editorial_status
from content.gate import run_content_hard_gate
from content.models import (
    ContentCandidateStatus,
    ContentStatement,
    ContentType,
    EditorialStatus,
    NumericKind,
    StatementKind,
)
from content.package import PackageError, build_publish_ready_package
from content.store import ContentCandidateStore
from publishing.editorial_gate import EditorialGateErrorCode
from research.atom_store import ResearchAtomStore
from research.claim_review import ClaimReviewError, set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStatus, KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus

# Keep fixture primary signals inside the Daily 48h freshness window without
# freezing production clocks or hardcoding calendar dates that drift.
_FIXTURE_TZ = ZoneInfo("Asia/Shanghai")
_FRESH_WITHIN_WINDOW = timedelta(hours=1)


def _fresh_published_at(*, age: timedelta = _FRESH_WITHIN_WINDOW) -> str:
    return (datetime.now(_FIXTURE_TZ) - age).isoformat(timespec="seconds")


def _verified_atoms(
    tmp_path: Path,
    *,
    url: str,
    excerpt: str,
    title: str = "t",
    published_at: str | None = None,
):
    atoms = news_to_research_atoms(
        {
            "title": title,
            "url": url,
            "source_name": "Fixture",
            "published_at": published_at or _fresh_published_at(),
            "excerpt": excerpt,
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": "cand-fix",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={
            "intake": "discovery",
            "candidate_id": "cand-fix",
            "source_tier": "B",
            "source_cluster_ids": ["cluster-a"],
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
        log_path=tmp_path / "claim_log.jsonl",
        persist=True,
    )
    return store, atoms.claims[0].id


def test_only_verified_claim_enters_knowledge(tmp_path: Path):
    store, claim_id = _verified_atoms(tmp_path, url="https://ex.com/a", excerpt="友宝扩大智能柜投放。")
    draft = news_to_research_atoms(
        {
            "title": "draft",
            "url": "https://ex.com/draft",
            "source_name": "x",
            "excerpt": "draft claim text",
        }
    )
    store.upsert_atoms(source=draft.source, evidence=draft.evidence, claims=draft.claims)
    knowledge = KnowledgeStore(tmp_path / "knowledge.json")
    rows = sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    active = [r for r in rows if r.status is KnowledgeStatus.ACTIVE]
    assert len(active) == 1
    assert active[0].claim_id == claim_id
    # stable identity
    again = sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    assert again[0].knowledge_id == active[0].knowledge_id


def test_rejected_claim_invalidates_knowledge(tmp_path: Path):
    store, claim_id = _verified_atoms(tmp_path, url="https://ex.com/b", excerpt="足够长的已验证正文。")
    knowledge = KnowledgeStore(tmp_path / "knowledge.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    set_claim_status(
        store,
        claim_id,
        ClaimStatus.REJECTED,
        reviewer="bob",
        reason="revisit",
        log_path=tmp_path / "claim_log.jsonl",
        persist=True,
    )
    rows = sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.get_by_claim(claim_id)
    assert rec is not None
    assert rec.status is KnowledgeStatus.INVALIDATED
    assert knowledge.list_active() == []


def test_syndication_independent_source_count(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/c", excerpt="转载聚类测试正文。")
    # force 10 syndicated urls but one cluster
    claim = next(iter(store.claims.values()))
    store.lineage[claim.id]["source_cluster_ids"] = ["cluster-same"] * 10
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    assert rec.independent_source_count == 1


def test_daily_multi_signal_fails(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/d", excerpt="主信号正文足够长。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge(
        [rec],
        content_type=ContentType.DAILY,
        primary_signals=["信号A", "信号B", "信号C"],
    )
    cand.metadata["extra_signals"] = ["信号B", "信号C"]
    build_internal_draft(cand)
    result = run_content_hard_gate(cand, atom_store=store)
    assert not result.passed
    assert result.has_error(EditorialGateErrorCode.MULTI_SIGNAL_DAILY)
    assert cand.status is ContentCandidateStatus.GATE_FAILED


def test_dongpeng_causal_overreach_fails(tmp_path: Path):
    store, _ = _verified_atoms(
        tmp_path,
        url="https://ex.com/dongpeng",
        excerpt="东鹏饮料营收与净利润增长。",
        title="东鹏财报",
    )
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    # Replace statement with unsupported causal leap
    cand.statements = [
        ContentStatement(
            kind=StatementKind.FACT,
            text="东鹏饮料营收与净利润增长，因此智能柜渠道动销强",
            claim_ids=[rec.claim_id],
            numeric_kind="SOURCE_FACT",
        )
    ]
    cand.metadata["causal_overreach"] = True
    build_internal_draft(cand)
    result = run_content_hard_gate(cand, atom_store=store)
    assert result.has_error(EditorialGateErrorCode.UNSUPPORTED_CAUSAL_INFERENCE)


def test_experiment_parameter_labeled_pass_and_unlabeled_fail(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/e", excerpt="主事实正文足够长。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    cand.statements.append(
        ContentStatement(
            kind=StatementKind.EXPERIMENT_PARAMETER,
            text="建议 10台柜 / 7天 / +5个百分点 作为试点参数",
            claim_ids=[rec.claim_id],
            numeric_kind=NumericKind.EXPERIMENT_PARAMETER.value,
            labeled_experiment=True,
        )
    )
    build_internal_draft(cand)
    ok = run_content_hard_gate(cand, atom_store=store)
    assert ok.passed

    cand2 = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    cand2.statements.append(
        ContentStatement(
            kind=StatementKind.EXPERIMENT_PARAMETER,
            text="行业标准应为 10台柜连续 7天提升 5个百分点",
            claim_ids=[rec.claim_id],
            numeric_kind=NumericKind.EXPERIMENT_PARAMETER.value,
            labeled_experiment=False,
        )
    )
    build_internal_draft(cand2)
    bad = run_content_hard_gate(cand2, atom_store=store)
    assert bad.has_error(EditorialGateErrorCode.UNLABELED_EXPERIMENT_PARAMETER)


def test_unsupported_numeric_fails(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/f", excerpt="主事实正文足够长。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    cand.statements.append(
        ContentStatement(
            kind=StatementKind.FACT,
            text="Prediction 70% 且连续上涨第3天",
            claim_ids=[rec.claim_id],
            numeric_kind=None,
        )
    )
    build_internal_draft(cand)
    result = run_content_hard_gate(cand, atom_store=store)
    assert result.has_error(EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM)


def test_snippet_evidence_fails(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/g", excerpt="主事实正文足够长。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    cand.metadata["evidence_source_type"] = "search_snippet"
    build_internal_draft(cand)
    result = run_content_hard_gate(cand, atom_store=store)
    assert result.has_error(EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE)


def test_stale_primary_signal_fails(tmp_path: Path):
    """Daily gate must reject primary signals older than the 48h window."""
    store, _ = _verified_atoms(
        tmp_path,
        url="https://ex.com/stale",
        excerpt="过期主信号正文足够长。",
        published_at=_fresh_published_at(age=timedelta(hours=72)),
    )
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    build_internal_draft(cand)
    result = run_content_hard_gate(cand, atom_store=store)
    assert not result.passed
    assert result.has_error(EditorialGateErrorCode.STALE_PRIMARY_SIGNAL)


def test_future_publication_fails(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/h", excerpt="主事实正文足够长。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    build_internal_draft(cand)
    cand.draft["published_at"] = "2099-01-01"
    result = run_content_hard_gate(cand, atom_store=store, now_date="2026-08-08")
    assert result.has_error(EditorialGateErrorCode.FUTURE_PUBLICATION)


def test_same_date_insight_pass_daily_fail_isolation(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/i", excerpt="同一主题已验证事实。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    insight = build_candidate_from_knowledge([rec], content_type=ContentType.INSIGHT, topic="智能柜")
    daily = build_candidate_from_knowledge(
        [rec],
        content_type=ContentType.DAILY,
        primary_signals=["A", "B", "C"],
    )
    daily.metadata["extra_signals"] = ["B", "C"]
    build_internal_draft(insight)
    build_internal_draft(daily)
    insight_gate = run_content_hard_gate(insight, atom_store=store)
    daily_gate = run_content_hard_gate(daily, atom_store=store)
    assert insight_gate.passed
    assert not daily_gate.passed
    assert insight.content_id != daily.content_id


def test_editorial_cannot_approve_gate_fail_and_package_flow(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/j", excerpt="可用于发布准备的已验证事实。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    build_editorial_brief(cand)
    build_internal_draft(cand)
    run_content_hard_gate(cand, atom_store=store)
    assert cand.status is ContentCandidateStatus.READY_FOR_EDITORIAL

    # Gate-fail cannot approve
    bad = build_candidate_from_knowledge(
        [rec], content_type=ContentType.DAILY, primary_signals=["x", "y"]
    )
    bad.metadata["extra_signals"] = ["y"]
    build_internal_draft(bad)
    run_content_hard_gate(bad, atom_store=store)
    try:
        set_editorial_status(bad, EditorialStatus.APPROVED, reviewer="editor")
        raise AssertionError("should fail")
    except ClaimReviewError as exc:
        assert exc.code == "EDITORIAL_APPROVE_REQUIRES_GATE_PASS"

    set_editorial_status(
        cand,
        EditorialStatus.APPROVED,
        reviewer="editor",
        reason="ready",
        log_path=tmp_path / "editorial.jsonl",
    )
    package = build_publish_ready_package(cand)
    assert package["status"] == "READY_FOR_CHANNEL_RENDER"
    assert package["wechat_published"] is False
    assert package["website_published"] is False

    # pending cannot package
    pending = build_candidate_from_knowledge([rec], content_type=ContentType.INSIGHT)
    build_internal_draft(pending)
    run_content_hard_gate(pending, atom_store=store)
    try:
        build_publish_ready_package(pending)
        raise AssertionError("pending should not package")
    except PackageError as exc:
        assert exc.code == "EDITORIAL_NOT_APPROVED"


def test_derived_metric_requires_formula(tmp_path: Path):
    store, _ = _verified_atoms(tmp_path, url="https://ex.com/k", excerpt="单柜日均销售额 120 元。")
    knowledge = KnowledgeStore(tmp_path / "k.json")
    sync_knowledge_from_atoms(atom_store=store, knowledge_store=knowledge, persist=True)
    rec = knowledge.list_active()[0]
    cand = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    cand.statements.append(
        ContentStatement(
            kind=StatementKind.FACT,
            text="推算毛利率为 35%",
            claim_ids=[rec.claim_id],
            numeric_kind="DERIVED_METRIC",
            formula="",
            inputs=[],
        )
    )
    build_internal_draft(cand)
    result = run_content_hard_gate(cand, atom_store=store)
    assert result.has_error(EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM)

    cand2 = build_candidate_from_knowledge([rec], content_type=ContentType.DAILY)
    cand2.statements.append(
        ContentStatement(
            kind=StatementKind.FACT,
            text="推算毛利率为 35%",
            claim_ids=[rec.claim_id],
            numeric_kind="DERIVED_METRIC",
            formula="(price-cost)/price",
            inputs=["price", "cost"],
        )
    )
    build_internal_draft(cand2)
    ok = run_content_hard_gate(cand2, atom_store=store)
    assert ok.passed
