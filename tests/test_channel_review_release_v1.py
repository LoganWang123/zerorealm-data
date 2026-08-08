"""Channel Review + Publisher Preflight tests (no real publish)."""

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
from content.publisher_preflight import (
    build_release_preflight,
    build_website_publish_plan,
    publisher_invoke_guard,
)
from content.release_candidate import (
    ChannelReviewStatus,
    ReleaseCandidateError,
    ReleaseCandidateStatus,
    assert_ready_for_publish,
    build_release_candidate,
    check_channel_review_preconditions,
    set_channel_review,
)
from research.atom_store import ResearchAtomStore
from research.claim_review import ClaimReviewError, set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus


def _ready_rc(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    atoms = news_to_research_atoms(
        {
            "title": "t",
            "url": "https://ex.com/rc",
            "source_name": "Fixture",
            "published_at": "2026-08-07T10:00:00+08:00",
            "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量。",
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": "cand-rc",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={
            "intake": "discovery",
            "candidate_id": "cand-rc",
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
    return cand, rc, tmp_path / "channel.jsonl"


def test_channel_review_pending_by_default(tmp_path, monkeypatch):
    _, rc, _ = _ready_rc(tmp_path, monkeypatch)
    assert rc.status is ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW
    assert rc.website_review["status"] == "PENDING"
    assert rc.wechat_review["status"] == "PENDING"


def test_one_channel_approved_not_ready_for_publish(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="ok", log_path=log
    )
    assert rc.status is not ReleaseCandidateStatus.READY_FOR_PUBLISH
    with pytest.raises(ReleaseCandidateError) as exc:
        assert_ready_for_publish(rc)
    assert exc.value.code == "CHANNEL_REVIEW_REQUIRED"


def test_both_channels_approved_ready_for_publish(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    assert rc.status is ReleaseCandidateStatus.READY_FOR_PUBLISH
    assert_ready_for_publish(rc)


def test_invalid_artifact_cannot_approve(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    rc.website_artifact = {}
    with pytest.raises(ReleaseCandidateError) as exc:
        set_channel_review(
            rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="x", log_path=log
        )
    assert exc.value.code == "CHANNEL_REVIEW_PRECONDITION_FAILED"


def test_reviewer_required_and_forbidden(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    with pytest.raises(ClaimReviewError):
        set_channel_review(
            rc, "website", ChannelReviewStatus.APPROVED, reviewer="AI", reason="x", log_path=log
        )
    with pytest.raises(ClaimReviewError):
        set_channel_review(
            rc, "website", ChannelReviewStatus.APPROVED, reviewer="cursor", reason="x", log_path=log
        )
    with pytest.raises(ClaimReviewError):
        set_channel_review(
            rc, "website", ChannelReviewStatus.APPROVED, reviewer=None, reason="x", log_path=log
        )


def test_channel_review_append_only_audit(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="ok", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.NEEDS_EDIT, reviewer="bob", reason="fix", log_path=log
    )
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert "review_id" in lines[0]
    assert "artifact_hash" in lines[0]
    assert "content_fingerprint" in lines[0]
    assert "old_status" in lines[0]


def test_publisher_rejects_before_channel_review(tmp_path, monkeypatch):
    _, rc, _ = _ready_rc(tmp_path, monkeypatch)
    with pytest.raises(ReleaseCandidateError) as exc:
        publisher_invoke_guard(rc, dry_run=True)
    assert exc.value.code == "CHANNEL_REVIEW_REQUIRED"


def test_publisher_dry_run_zero_network(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    plan = build_release_preflight(rc, out_dir=tmp_path / "plan")
    assert plan["dry_run"] is True
    assert plan["wechat_api_called"] is False
    assert plan["website_production_written"] is False
    assert plan["website_plan"]["network_calls"] == []
    assert plan["wechat_plan"]["freepublish"] is False
    assert plan["wechat_plan"]["create_draft"] is False
    assert plan["website_plan"]["target_route"] == "/insight/smart-cabinet-five-process-metrics"
    assert not plan["website_plan"]["target_route"].startswith("/daily/")
    assert (tmp_path / "plan" / "release-plan.json").is_file()


def test_insight_never_maps_to_daily_route(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    website = build_website_publish_plan(rc)
    assert website["content_type"] == "insight"
    assert website["target_route"].startswith("/insight/")


def test_consistency_fail_blocks_preconditions(tmp_path, monkeypatch):
    _, rc, _ = _ready_rc(tmp_path, monkeypatch)
    rc.channel_consistency_result = {"passed": False}
    codes = check_channel_review_preconditions(rc, "website")
    assert "CHANNEL_CONSISTENCY_FAILED" in codes


def test_gate_fail_never_ready(tmp_path, monkeypatch):
    _, rc, log = _ready_rc(tmp_path, monkeypatch)
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    rc.gate_result = {"passed": False}
    with pytest.raises(ReleaseCandidateError) as exc:
        set_channel_review(
            rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
        )
    assert exc.value.code == "GATE_NOT_PASSED"
