"""Release Orchestrator v1 — unified state, preflight, review integrity (no real publish)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from content.publisher_preflight import (
    build_release_preflight,
    build_website_publish_plan,
    build_wechat_publish_plan,
)
from content.release_candidate import (
    ChannelReviewStatus,
    ReleaseCandidate,
    ReleaseCandidateError,
    ReleaseCandidateStatus,
    assert_ready_for_publish,
    make_release_candidate_id,
)
from utils.helpers import now_iso


class ReleaseState(str, Enum):
    DRAFT = "DRAFT"
    GATE_FAILED = "GATE_FAILED"
    EDITORIAL_REVIEW = "EDITORIAL_REVIEW"
    EDITORIAL_APPROVED = "EDITORIAL_APPROVED"
    RENDERED = "RENDERED"
    CHANNEL_CHECKED = "CHANNEL_CHECKED"
    CHANNEL_REVIEW = "CHANNEL_REVIEW"
    READY_FOR_PUBLISH = "READY_FOR_PUBLISH"
    PUBLISHING = "PUBLISHING"  # defined only — not executed this round
    PARTIALLY_PUBLISHED = "PARTIALLY_PUBLISHED"  # defined only
    PUBLISHED = "PUBLISHED"  # defined only
    FAILED = "FAILED"
    REVIEW_STALE = "REVIEW_STALE"


@dataclass
class ChannelPublishState:
    """Future recovery model for partial publish — no side effects this round."""

    rendered: bool = False
    reviewed: bool = False
    publishing: bool = False
    published: bool = False
    failed: bool = False
    last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "rendered": self.rendered,
            "reviewed": self.reviewed,
            "publishing": self.publishing,
            "published": self.published,
            "failed": self.failed,
            "last_error": self.last_error,
        }


@dataclass
class ReleaseStatus:
    release_candidate_id: str
    content_id: str
    content_type: str
    slug: str
    revision: str
    state: ReleaseState
    ready: bool
    blocking_reasons: list[str] = field(default_factory=list)
    content_fingerprint: str = ""
    artifact_hashes: dict = field(default_factory=dict)
    website: dict = field(default_factory=dict)
    wechat: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)
    checked_at: str = ""

    def to_dict(self) -> dict:
        return {
            "release_candidate_id": self.release_candidate_id,
            "content_id": self.content_id,
            "content_type": self.content_type,
            "slug": self.slug,
            "revision": self.revision,
            "state": self.state.value,
            "ready": self.ready,
            "result": "READY" if self.ready else "BLOCKED",
            "blocking_reasons": list(self.blocking_reasons),
            "content_fingerprint": self.content_fingerprint,
            "artifact_hashes": dict(self.artifact_hashes),
            "website": dict(self.website),
            "wechat": dict(self.wechat),
            "details": dict(self.details),
            "checked_at": self.checked_at,
        }


def compute_artifact_hash(artifact: dict | None) -> str:
    raw = json.dumps(artifact or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def content_revision_fingerprint(
    *,
    content_id: str,
    content_type: str,
    slug: str,
    body_fingerprint: str,
    claim_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
    media_ids: list[str] | None = None,
) -> str:
    payload = {
        "content_id": content_id,
        "content_type": content_type,
        "slug": slug,
        "body_fingerprint": body_fingerprint,
        "claim_ids": sorted(claim_ids or []),
        "source_ids": sorted(source_ids or []),
        "media_ids": sorted(media_ids or []),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_release_candidate_id(content_id: str, revision: str) -> str:
    """Same content revision always yields the same RC identity."""
    return make_release_candidate_id(content_id, revision)


def map_rc_to_release_state(rc: ReleaseCandidate) -> ReleaseState:
    if rc.metadata.get("review_stale"):
        return ReleaseState.REVIEW_STALE
    status = rc.status
    if status is ReleaseCandidateStatus.READY_FOR_PUBLISH:
        return ReleaseState.READY_FOR_PUBLISH
    if status is ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW:
        return ReleaseState.CHANNEL_REVIEW
    if status is ReleaseCandidateStatus.CHANNEL_CHECK_PASSED:
        return ReleaseState.CHANNEL_CHECKED
    if status is ReleaseCandidateStatus.RENDERED:
        return ReleaseState.RENDERED
    if status is ReleaseCandidateStatus.EDITORIAL_APPROVED:
        return ReleaseState.EDITORIAL_APPROVED
    if status is ReleaseCandidateStatus.GATE_PASSED:
        return ReleaseState.EDITORIAL_REVIEW
    if status is ReleaseCandidateStatus.REJECTED:
        return ReleaseState.FAILED
    gate = rc.gate_result or {}
    if gate and gate.get("passed") is False:
        return ReleaseState.GATE_FAILED
    return ReleaseState.DRAFT


def invalidate_channel_reviews_if_stale(
    rc: ReleaseCandidate,
    *,
    current_fingerprint: str,
    current_website_hash: str,
    current_wechat_hash: str,
) -> list[str]:
    """If content/artifacts changed after APPROVED review, force PENDING + REVIEW_STALE."""
    reasons: list[str] = []
    approved_fp = None
    for review in (rc.website_review, rc.wechat_review):
        if (review or {}).get("status") == ChannelReviewStatus.APPROVED.value:
            approved_fp = review.get("content_fingerprint") or approved_fp
            break

    if approved_fp and current_fingerprint and approved_fp != current_fingerprint:
        reasons.append("REVIEW_STALE")
        for channel, attr in (("website", "website_review"), ("wechat", "wechat_review")):
            review = getattr(rc, attr) or {}
            if review.get("status") == ChannelReviewStatus.APPROVED.value:
                review = dict(review)
                review["status"] = ChannelReviewStatus.PENDING.value
                review["invalidated_reason"] = "REVIEW_STALE"
                setattr(rc, attr, review)
                channel_state = getattr(rc, channel) or {}
                channel_state["reviewed"] = False
                setattr(rc, channel, channel_state)
        rc.status = ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW
        rc.metadata["review_stale"] = True

    for channel, attr, current in (
        ("website", "website_review", current_website_hash),
        ("wechat", "wechat_review", current_wechat_hash),
    ):
        review = getattr(rc, attr) or {}
        if review.get("status") != ChannelReviewStatus.APPROVED.value:
            continue
        stored = review.get("artifact_hash") or ""
        if stored and current and stored != current:
            reasons.append("ARTIFACT_CHANGED_AFTER_REVIEW")
            review = dict(review)
            review["status"] = ChannelReviewStatus.PENDING.value
            review["invalidated_reason"] = "ARTIFACT_CHANGED_AFTER_REVIEW"
            setattr(rc, attr, review)
            channel_state = getattr(rc, channel) or {}
            channel_state["reviewed"] = False
            setattr(rc, channel, channel_state)
            rc.status = ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW
            rc.metadata["review_stale"] = True
    return sorted(set(reasons))


class ReleaseOrchestrator:
    """Single place for readiness checks — CLI/publisher should not re-implement."""

    def status(self, rc: ReleaseCandidate) -> ReleaseStatus:
        return self.preflight(rc, write_plans=False)

    def preflight(self, rc: ReleaseCandidate, *, write_plans: bool = False) -> ReleaseStatus:
        blocking: list[str] = []
        details: dict = {
            "content_identity": {
                "content_id": rc.content_id,
                "content_type": rc.content_type,
                "slug": rc.slug,
                "revision": rc.revision,
            },
            "research_provenance": dict(rc.research_provenance),
            "gate": dict(rc.gate_result),
            "editorial": {
                "reviewer": rc.editorial_reviewer,
                "reviewed_at": rc.editorial_reviewed_at,
            },
            "website_artifact": bool(rc.website_artifact),
            "wechat_artifact": bool(rc.wechat_artifact),
            "channel_consistency": dict(rc.channel_consistency_result),
            "website_review": dict(rc.website_review),
            "wechat_review": dict(rc.wechat_review),
        }

        website_hash = compute_artifact_hash(rc.website_artifact)
        wechat_hash = compute_artifact_hash(rc.wechat_artifact)
        fp = rc.content_fingerprint or ""
        stale_reasons = invalidate_channel_reviews_if_stale(
            rc,
            current_fingerprint=fp,
            current_website_hash=website_hash,
            current_wechat_hash=wechat_hash,
        )
        blocking.extend(stale_reasons)

        gate = rc.gate_result or {}
        if not gate.get("passed"):
            blocking.append("GATE_NOT_PASSED")
        if not rc.editorial_reviewer:
            blocking.append("EDITORIAL_REVIEW_REQUIRED")
        if not rc.website_artifact:
            blocking.append("WEBSITE_ARTIFACT_MISSING")
        if not rc.wechat_artifact:
            blocking.append("WECHAT_ARTIFACT_MISSING")
        consistency = rc.channel_consistency_result or {}
        if not consistency.get("passed"):
            blocking.append("CHANNEL_CONSISTENCY_FAILED")
        if (rc.website_review or {}).get("status") != ChannelReviewStatus.APPROVED.value:
            blocking.append("WEBSITE_CHANNEL_REVIEW_REQUIRED")
        if (rc.wechat_review or {}).get("status") != ChannelReviewStatus.APPROVED.value:
            blocking.append("WECHAT_CHANNEL_REVIEW_REQUIRED")

        # Identity hard rule
        if rc.content_type == "insight":
            route = (rc.website_artifact or {}).get("route") or ""
            if route.startswith("/daily/"):
                blocking.append("CONTENT_TYPE_MISMATCH")

        # Stable identity check
        expected_id = stable_release_candidate_id(rc.content_id, rc.revision)
        if rc.release_candidate_id and rc.release_candidate_id != expected_id:
            blocking.append("RELEASE_IDENTITY_MISMATCH")

        ready = not blocking
        if ready:
            try:
                assert_ready_for_publish(rc)
            except ReleaseCandidateError as exc:
                ready = False
                blocking.append(exc.code)

        state = ReleaseState.READY_FOR_PUBLISH if ready else map_rc_to_release_state(rc)
        if "REVIEW_STALE" in blocking or "ARTIFACT_CHANGED_AFTER_REVIEW" in blocking:
            state = ReleaseState.REVIEW_STALE

        website_state = ChannelPublishState(
            rendered=bool(rc.website_artifact),
            reviewed=(rc.website_review or {}).get("status") == ChannelReviewStatus.APPROVED.value,
            published=bool((rc.website or {}).get("published")),
        )
        wechat_state = ChannelPublishState(
            rendered=bool(rc.wechat_artifact),
            reviewed=(rc.wechat_review or {}).get("status") == ChannelReviewStatus.APPROVED.value,
            published=bool((rc.wechat or {}).get("published")),
        )

        details["publisher_readiness"] = "READY" if ready else "BLOCKED"
        details["idempotent_release_candidate_id"] = expected_id

        if write_plans and ready:
            details["plans"] = build_release_preflight(rc)

        return ReleaseStatus(
            release_candidate_id=rc.release_candidate_id,
            content_id=rc.content_id,
            content_type=rc.content_type,
            slug=rc.slug,
            revision=rc.revision,
            state=state,
            ready=ready,
            blocking_reasons=sorted(set(blocking)),
            content_fingerprint=fp,
            artifact_hashes={"website": website_hash, "wechat": wechat_hash},
            website=website_state.to_dict(),
            wechat=wechat_state.to_dict(),
            details=details,
            checked_at=now_iso(),
        )

    def plan(self, rc: ReleaseCandidate) -> dict:
        status = self.preflight(rc, write_plans=False)
        if not status.ready:
            raise ReleaseCandidateError(
                "RELEASE_BLOCKED",
                f"Cannot build publish plan: {', '.join(status.blocking_reasons)}",
            )
        return {
            "status": status.to_dict(),
            "website_plan": build_website_publish_plan(rc),
            "wechat_plan": build_wechat_publish_plan(rc),
            "dry_run": True,
            "network_calls": [],
        }

    def dry_run(self, rc: ReleaseCandidate, *, out_dir: str | Path | None = None) -> dict:
        status = self.preflight(rc, write_plans=False)
        if not status.ready:
            raise ReleaseCandidateError(
                "RELEASE_BLOCKED",
                f"Dry-run blocked: {', '.join(status.blocking_reasons)}",
            )
        plans = build_release_preflight(rc, out_dir=out_dir)
        return {
            "status": status.to_dict(),
            "plans": plans,
            "dry_run": True,
            "publisher_invoked": False,
            "wechat_api_called": False,
            "website_production_written": False,
            "network_calls": [],
        }

    def bump_revision_on_change(
        self,
        rc: ReleaseCandidate,
        *,
        new_fingerprint: str,
    ) -> ReleaseCandidate:
        """Content change increments revision and invalidates prior channel reviews."""
        if new_fingerprint and new_fingerprint != rc.content_fingerprint:
            try:
                rev = int(rc.revision)
            except ValueError:
                rev = 1
            rc.revision = str(rev + 1)
            rc.content_fingerprint = new_fingerprint
            rc.release_candidate_id = stable_release_candidate_id(rc.content_id, rc.revision)
            rc.website_review = {
                "status": ChannelReviewStatus.PENDING.value,
                "reviewer": "",
                "reviewed_at": "",
            }
            rc.wechat_review = {
                "status": ChannelReviewStatus.PENDING.value,
                "reviewer": "",
                "reviewed_at": "",
            }
            rc.website["reviewed"] = False
            rc.wechat["reviewed"] = False
            rc.status = ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW
            rc.metadata["review_stale"] = True
            rc.updated_at = now_iso()
        return rc


def partial_publish_model_example() -> dict:
    """Documented recovery semantics for future real publishers (no side effects)."""
    return {
        "state": ReleaseState.PARTIALLY_PUBLISHED.value,
        "channels": {
            "website": ChannelPublishState(published=True, reviewed=True, rendered=True).to_dict(),
            "wechat": ChannelPublishState(
                published=False, failed=True, last_error="WECHAT_API_FAILED", reviewed=True, rendered=True
            ).to_dict(),
        },
        "retry_policy": {
            "do_not_duplicate_release_identity": True,
            "retry_failed_channels_only": True,
            "release_candidate_id_stable": True,
        },
        "note": "Model only — real external publish not executed in Orchestrator v1",
    }
