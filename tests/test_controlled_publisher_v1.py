"""Controlled Publisher v1 — safety, transactions, receipts, rehearsal (zero network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from content.audit import audit_structured_draft
from content.brief import build_editorial_brief
from content.candidates import build_candidate_from_knowledge
from content.channel_render import render_channels
from content.consistency import check_channel_consistency
from content.controlled_publish.confirmation import build_confirmation_token, validate_confirmation_token
from content.controlled_publish.errors import (
    CONFIRMATION_INVALID,
    CONTENT_ALREADY_EXISTS,
    FREEPUBLISH_NOT_APPROVED,
    MEDIA_NOT_APPROVED,
    PUBLISH_DISABLED,
    RELEASE_LOCKED,
    ControlledPublishError,
)
from content.controlled_publish.factory import ControlledPublisherFactory
from content.controlled_publish.lock import ReleaseLockStore
from content.controlled_publish.modes import ExecutionMode, publish_disabled
from content.controlled_publish.receipt import ReceiptStore
from content.controlled_publish.service import ControlledPublishService
from content.controlled_publish.transaction import ChannelPublishState, TransactionOverallState, TransactionStore
from content.controlled_publish.verify import MockWeChatVerifier, MockWebsiteVerifier
from content.controlled_publish.wechat_adapter import WeChatPublishStep
from content.editorial_review import set_editorial_status
from content.generator import generate_controlled_draft
from content.models import ContentType, EditorialStatus, make_content_id
from content.release_candidate import (
    ChannelReviewStatus,
    ReleaseCandidateStatus,
    build_release_candidate,
    set_channel_review,
)
from research.atom_store import ResearchAtomStore
from research.claim_review import set_claim_status
from research.intake import news_to_research_atoms
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms
from research.models import ClaimStatus

ENABLE = {"PUBLISH_DISABLED": "false"}


def _ready_rc(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    atoms = news_to_research_atoms(
        {
            "title": "t",
            "url": "https://ex.com/pub",
            "source_name": "Fixture",
            "published_at": "2026-08-07T10:00:00+08:00",
            "excerpt": "缺货率与补货及时率更能反映智能柜终端经营质量。",
            "discovery_provider": "fake",
            "discovery_query": "智能柜",
            "discovery_candidate_id": "cand-pub",
        }
    )
    store = ResearchAtomStore(tmp_path / "atoms.json")
    store.upsert_atoms(
        source=atoms.source,
        evidence=atoms.evidence,
        claims=atoms.claims,
        lineage={
            "intake": "discovery",
            "candidate_id": "cand-pub",
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
    log = tmp_path / "ch.jsonl"
    set_channel_review(
        rc, "website", ChannelReviewStatus.APPROVED, reviewer="alice", reason="w", log_path=log
    )
    set_channel_review(
        rc, "wechat", ChannelReviewStatus.APPROVED, reviewer="alice", reason="c", log_path=log
    )
    assert rc.status is ReleaseCandidateStatus.READY_FOR_PUBLISH
    return cand, rc, tmp_path


def _svc(tmp_path: Path, **kwargs) -> ControlledPublishService:
    root = tmp_path / "cp"
    return ControlledPublishService(root=root, **kwargs)


def test_publish_disabled_default():
    assert publish_disabled({}) is True
    assert publish_disabled({"PUBLISH_DISABLED": "true"}) is True
    assert publish_disabled({"PUBLISH_DISABLED": "false"}) is False


def test_dry_run_allowed_without_kill_switch_off(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    out = _svc(path).execute(rc, mode=ExecutionMode.DRY_RUN)
    assert out["executed"] is False
    assert out["network_calls"] == []
    assert out["website_production_writes"] == 0
    assert out["wechat_api_calls"] == 0


def test_production_blocked_when_publish_disabled(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    token = build_confirmation_token(rc)
    with pytest.raises(ControlledPublishError) as exc:
        _svc(path).execute(
            rc,
            mode=ExecutionMode.PRODUCTION,
            confirm=token,
            freepublish_approved=True,
            env={"PUBLISH_DISABLED": "true"},
        )
    assert exc.value.code == PUBLISH_DISABLED


def test_production_blocked_without_confirmation(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    with pytest.raises(ControlledPublishError) as exc:
        _svc(path).execute(
            rc,
            mode=ExecutionMode.PRODUCTION,
            confirm=None,
            freepublish_approved=True,
            env=ENABLE,
        )
    assert exc.value.code in ("CONFIRMATION_REQUIRED", CONFIRMATION_INVALID)


def test_confirmation_tied_to_revision_fingerprint(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    token = build_confirmation_token(rc)
    validate_confirmation_token(rc, token)
    with pytest.raises(ControlledPublishError) as exc:
        validate_confirmation_token(rc, "yes")
    assert exc.value.code == CONFIRMATION_INVALID
    rc.content_fingerprint = "changed-fingerprint"
    with pytest.raises(ControlledPublishError) as exc2:
        validate_confirmation_token(rc, token)
    assert exc2.value.code == CONFIRMATION_INVALID


def test_website_insight_and_daily_paths(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    pub = ControlledPublisherFactory().website()
    prepared = pub.prepare(rc)
    assert prepared["content_path"] == "content/insight/smart-cabinet-five-process-metrics.mdx"
    assert prepared["expected_route"] == "/insight/smart-cabinet-five-process-metrics"
    assert not prepared["content_path"].startswith("content/daily/")

    from copy import deepcopy

    daily = deepcopy(rc)
    daily.content_type = "daily"
    daily.slug = "2026-08-01"
    daily.content_id = make_content_id("daily", daily.slug)
    # rebuild plan pieces via adapter path helper
    assert pub.content_path(daily) == "content/daily/2026-08-01.mdx"


def test_insight_never_becomes_daily_path(tmp_path, monkeypatch):
    _, rc, _ = _ready_rc(tmp_path, monkeypatch)
    pub = ControlledPublisherFactory().website()
    assert rc.content_type == "insight"
    prepared = pub.prepare(rc)
    assert prepared["content_path"].startswith("content/insight/")
    assert prepared["expected_route"].startswith("/insight/")
    assert not prepared["expected_route"].startswith("/daily/")


def test_website_create_only_conflict(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    factory = ControlledPublisherFactory()
    pub = factory.website()
    prepared = pub.prepare(rc)
    receipt = pub.execute(rc, mode=ExecutionMode.STAGING, prepared=prepared, env=ENABLE)
    assert receipt.mock is True
    assert str(receipt.receipt_id).startswith("mock://")
    with pytest.raises(ControlledPublishError) as exc:
        pub.execute(rc, mode=ExecutionMode.STAGING, prepared=prepared, env=ENABLE)
    assert exc.value.code == CONTENT_ALREADY_EXISTS


def test_wechat_draft_freepublish_separated(tmp_path, monkeypatch):
    _, rc, _ = _ready_rc(tmp_path, monkeypatch)
    pub = ControlledPublisherFactory().wechat()
    draft = pub.execute(rc, mode=ExecutionMode.STAGING, step=WeChatPublishStep.CREATE_DRAFT, env=ENABLE)
    assert draft.details["step"] == "CREATE_DRAFT"
    with pytest.raises(ControlledPublishError) as exc:
        pub.execute(
            rc,
            mode=ExecutionMode.STAGING,
            step=WeChatPublishStep.FREEPUBLISH,
            freepublish_approved=False,
            existing_draft_receipt=draft,
            env=ENABLE,
        )
    assert exc.value.code == FREEPUBLISH_NOT_APPROVED
    # idempotent draft
    draft2 = pub.execute(rc, mode=ExecutionMode.STAGING, step=WeChatPublishStep.CREATE_DRAFT, env=ENABLE)
    assert draft2.details["draft_media_id"] == draft.details["draft_media_id"]


def test_wechat_media_pending_blocked(tmp_path, monkeypatch):
    _, rc, _ = _ready_rc(tmp_path, monkeypatch)
    rc.wechat_artifact = dict(rc.wechat_artifact or {})
    rc.wechat_artifact["media"] = [{"id": "m1", "status": "pending"}]
    pub = ControlledPublisherFactory().wechat()
    with pytest.raises(ControlledPublishError) as exc:
        pub.prepare(rc)
    assert exc.value.code == MEDIA_NOT_APPROVED


def test_lock_acquire_concurrent_and_release(tmp_path):
    store = ReleaseLockStore(tmp_path / "locks.json")
    lock = store.acquire("rc-1", owner="host:1", ttl_seconds=600)
    assert store.status("rc-1") is not None
    with pytest.raises(ControlledPublishError) as exc:
        store.acquire("rc-1", owner="host:2", ttl_seconds=600)
    assert exc.value.code == RELEASE_LOCKED
    store.release("rc-1", owner=lock.locked_by)
    assert store.status("rc-1") is None


def test_stale_lock_recovery(tmp_path):
    store = ReleaseLockStore(tmp_path / "locks.json")
    store.acquire("rc-2", owner="host:1", ttl_seconds=1, now_iso_ts="2026-08-08T10:00:00+00:00")
    # expire
    assert store.status("rc-2", now_ts=1_800_000_000) is None
    lock = store.acquire("rc-2", owner="host:2", ttl_seconds=600)
    assert lock.locked_by == "host:2"


def test_full_success_rehearsal(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    svc = _svc(path)
    token = build_confirmation_token(rc)
    out = svc.execute(
        rc,
        mode=ExecutionMode.STAGING,
        confirm=token,
        freepublish_approved=True,
        env=ENABLE,
    )
    assert out["network_calls"] == []
    assert out["website_production_writes"] == 0
    assert out["wechat_api_calls"] == 0
    txn = out["transaction"]
    assert txn["overall_state"] == TransactionOverallState.PUBLISHED.value
    assert txn["website_state"]["state"] == ChannelPublishState.SUCCEEDED.value
    assert txn["wechat_state"]["state"] == ChannelPublishState.SUCCEEDED.value
    assert all(str(r["receipt_id"]).startswith("mock://") for r in out["receipts"])

    # idempotent re-execute
    out2 = svc.execute(
        rc,
        mode=ExecutionMode.STAGING,
        confirm=token,
        freepublish_approved=True,
        env=ENABLE,
    )
    assert out2.get("idempotent") is True
    assert out2["transaction"]["transaction_id"] == txn["transaction_id"]


def test_partial_failure_and_retry(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    factory = ControlledPublisherFactory()
    svc = _svc(path, factory=factory)
    token = build_confirmation_token(rc)
    out = svc.execute(
        rc,
        mode=ExecutionMode.STAGING,
        confirm=token,
        freepublish_approved=False,
        env=ENABLE,
    )
    txn = out["transaction"]
    assert txn["overall_state"] == TransactionOverallState.PARTIALLY_PUBLISHED.value
    assert txn["website_state"]["state"] == ChannelPublishState.SUCCEEDED.value
    assert txn["wechat_state"]["state"] == ChannelPublishState.FAILED.value

    plan = svc.recovery_plan(txn["transaction_id"])
    assert "wechat" in plan["retry_channels"]
    assert "website" in plan["skip_channels"]

    website_patches_before = len(factory.website_backend.patches)
    retry = svc.retry(
        txn["transaction_id"],
        rc,
        channel="wechat",
        confirm=token,
        freepublish_approved=True,
        env=ENABLE,
    )
    assert retry["transaction"]["overall_state"] == TransactionOverallState.PUBLISHED.value
    assert len(factory.website_backend.patches) == website_patches_before

    skip = svc.retry(
        txn["transaction_id"],
        rc,
        channel="website",
        confirm=token,
        env=ENABLE,
    )
    assert skip.get("skipped") is True


def test_verify_failure_semantics(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    svc = _svc(path, website_verifier=MockWebsiteVerifier(force_fail=True))
    token = build_confirmation_token(rc)
    out = svc.execute(
        rc,
        mode=ExecutionMode.STAGING,
        confirm=token,
        channels=["website"],
        freepublish_approved=True,
        env=ENABLE,
    )
    assert out["transaction"]["website_state"]["state"] == ChannelPublishState.VERIFICATION_FAILED.value


def test_stale_review_blocks_publish(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    token = build_confirmation_token(rc)
    rc.content_fingerprint = "mutated-after-ready"
    with pytest.raises(ControlledPublishError) as conf_exc:
        validate_confirmation_token(rc, token)
    assert conf_exc.value.code == CONFIRMATION_INVALID

    from content.orchestrator import ReleaseOrchestrator

    status = ReleaseOrchestrator().preflight(rc)
    assert status.ready is False
    assert "REVIEW_STALE" in status.blocking_reasons

    svc = _svc(path)
    with pytest.raises(ControlledPublishError) as exc:
        svc.execute(
            rc,
            mode=ExecutionMode.STAGING,
            confirm=token,
            freepublish_approved=True,
            env=ENABLE,
        )
    assert exc.value.code in (CONFIRMATION_INVALID, "NOT_READY_FOR_PUBLISH")


def test_receipt_store_immutable_reuse(tmp_path):
    store = ReceiptStore(tmp_path / "r.jsonl")
    from content.controlled_publish.receipt import mock_website_receipt

    r1 = mock_website_receipt(
        release_candidate_id="rc",
        content_id="c",
        revision="1",
        artifact_hash="a",
        fingerprint="f",
        route="/insight/x",
        content_path="content/insight/x.mdx",
    )
    a = store.append(r1)
    b = store.append(r1)
    assert a.receipt_id == b.receipt_id
    lines = (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_transaction_store_durable(tmp_path, monkeypatch):
    _, rc, path = _ready_rc(tmp_path, monkeypatch)
    svc = _svc(path)
    token = build_confirmation_token(rc)
    out = svc.execute(
        rc,
        mode=ExecutionMode.STAGING,
        confirm=token,
        freepublish_approved=True,
        env=ENABLE,
    )
    txn_id = out["transaction"]["transaction_id"]
    reloaded = TransactionStore(path / "cp" / "transactions.json").get(txn_id)
    assert reloaded is not None
    assert reloaded.overall_state is TransactionOverallState.PUBLISHED
