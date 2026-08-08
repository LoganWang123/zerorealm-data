"""Release Orchestrator v1 tests — state machine, integrity, dry-run (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from content.audit import audit_structured_draft
from content.brief import build_editorial_brief
from content.candidates import build_candidate_from_knowledge
from content.channel_render import render_channels
from content.consistency import check_channel_consistency
from content.editorial_review import set_editorial_status
from content.generator import generate_controlled_draft
from content.models import ContentType, EditorialStatus, make_content_id
from content.orchestrator import (
    ReleaseOrchestrator,
    ReleaseState,
    content_revision_fingerprint,
    partial_publish_model_example,
    stable_release_candidate_id,
)
from content.release_candidate import (
    ChannelReviewStatus,
    ReleaseCandidateError,
    ReleaseCandidateStatus,
    build_release_candidate,
    set_channel_review,
)
from research.atom_store import ResearchAtomStore
from research.claim_review import set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus


def _rc(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    atoms = news_to_research_atoms(
        {
            "title": "t",
            "url": "https://ex.com/orch",
            "source_name": "Fixture",
            "published_at": "2026-08-07T10:00:00+08:00",
            "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量。",
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": "cand-orch",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={
            "intake": "discovery",
            "candidate_id": "cand-orch",
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
    build_editorial_brief(cand)
    draft = generate_controlled_draft(cand, atom_store=store)
    assert audit_structured_draft(cand, draft, atom_store=store).passed
    set_editorial_status(
        cand,
        EditorialStatus.APPROVED,
        reviewer="alice",
        reason="ok",
        log_path=tmp_path / "ed.jsonl",
    )
    render_channels(cand)
    assert check_channel_consistency(cand).passed
    rc = build_release_candidate(cand)
    return cand, rc, tmp_path / "ch.jsonl"


def test_preflight_blocks_before_channel_reviews(tmp_path, monkeypatch):
    _, rc, _ = _rc(tmp_path, monkeypatch)
    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is False
    assert status.state is ReleaseState.CHANNEL_REVIEW
    assert "WEBSITE_CHANNEL_REVIEW_REQUIRED" in status.blocking_reasons
    assert "WECHAT_CHANNEL_REVIEW_REQUIRED" in status.blocking_reasons


def test_gate_fail_blocked(tmp_path, monkeypatch):
    _, rc, _ = _rc(tmp_path, monkeypatch)
    rc.gate_result = {"passed": False}
    status = ReleaseOrchestrator().preflight(rc)
    assert "GATE_NOT_PASSED" in status.blocking_reasons


def test_editorial_pending_blocked(tmp_path, monkeypatch):
    _, rc, _ = _rc(tmp_path, monkeypatch)
    rc.editorial_reviewer = ""
    status = ReleaseOrchestrator().preflight(rc)
    assert "EDITORIAL_REVIEW_REQUIRED" in status.blocking_reasons


def test_one_channel_pending_blocked(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is False
    assert "WECHAT_CHANNEL_REVIEW_REQUIRED" in status.blocking_reasons


def test_both_approved_ready(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is True
    assert status.state is ReleaseState.READY_FOR_PUBLISH
    assert status.blocking_reasons == []


def test_content_changed_after_review_stale(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    assert rc.status is ReleaseCandidateStatus.READY_FOR_PUBLISH
    rc.content_fingerprint = "changed-fingerprint"
    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is False
    assert "REVIEW_STALE" in status.blocking_reasons
    assert status.state is ReleaseState.REVIEW_STALE
    assert rc.website_review["status"] == "PENDING"
    assert rc.wechat_review["status"] == "PENDING"


def test_artifact_hash_changed_blocked(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    rc.website_artifact = {**rc.website_artifact, "tampered": True}
    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is False
    assert "ARTIFACT_CHANGED_AFTER_REVIEW" in status.blocking_reasons


def test_revision_increments_and_invalidates(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    old_id = rc.release_candidate_id
    orch = ReleaseOrchestrator()
    orch.bump_revision_on_change(rc, new_fingerprint="fp-v2")
    assert rc.revision == "2"
    assert rc.release_candidate_id != old_id
    assert rc.release_candidate_id == stable_release_candidate_id(rc.content_id, "2")
    assert rc.website_review["status"] == "PENDING"
    status = orch.preflight(rc)
    assert status.ready is False


def test_idempotent_preflight_stable_identity(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    orch = ReleaseOrchestrator()
    a = orch.preflight(rc)
    b = orch.preflight(rc)
    assert a.release_candidate_id == b.release_candidate_id
    assert a.details["idempotent_release_candidate_id"] == rc.release_candidate_id
    assert a.content_id == b.content_id
    assert a.content_type == "insight"
    assert a.slug == "smart-cabinet-five-process-metrics"


def test_insight_never_maps_daily_in_dry_run(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    out = ReleaseOrchestrator().dry_run(rc, out_dir=tmp_path / "plans")
    assert out["dry_run"] is True
    assert out["network_calls"] == []
    assert out["wechat_api_called"] is False
    assert out["website_production_written"] is False
    assert out["plans"]["website_plan"]["target_route"].startswith("/insight/")
    assert not out["plans"]["website_plan"]["target_route"].startswith("/daily/")


def test_partial_publish_model_and_retry_identity():
    model = partial_publish_model_example()
    assert model["state"] == ReleaseState.PARTIALLY_PUBLISHED.value
    assert model["retry_policy"]["do_not_duplicate_release_identity"] is True
    assert model["channels"]["website"]["published"] is True
    assert model["channels"]["wechat"]["published"] is False


def test_content_type_mismatch_blocks(tmp_path, monkeypatch):
    _, rc, log = _rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    rc.website_artifact = {**rc.website_artifact, "route": "/daily/2026-08-08"}
    # artifact change also invalidates; either way blocked
    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is False
    assert (
        "CONTENT_TYPE_MISMATCH" in status.blocking_reasons
        or "ARTIFACT_CHANGED_AFTER_REVIEW" in status.blocking_reasons
    )


def test_fingerprint_helper_stable():
    a = content_revision_fingerprint(
        content_id="ct-1",
        content_type="insight",
        slug="s",
        body_fingerprint="fp",
        claim_ids=["c2", "c1"],
    )
    b = content_revision_fingerprint(
        content_id="ct-1",
        content_type="insight",
        slug="s",
        body_fingerprint="fp",
        claim_ids=["c1", "c2"],
    )
    assert a == b


def test_plan_blocked_raises(tmp_path, monkeypatch):
    _, rc, _ = _rc(tmp_path, monkeypatch)
    with pytest.raises(ReleaseCandidateError) as exc:
        ReleaseOrchestrator().plan(rc)
    assert exc.value.code == "RELEASE_BLOCKED"
