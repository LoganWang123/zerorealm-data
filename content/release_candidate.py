"""Release Candidate manifest + Channel Review — STOP before publish."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from content.consistency import check_channel_consistency
from content.models import ContentCandidate, EditorialStatus
from content.store import load_content_config
from research.claim_review import ClaimReviewError, resolve_reviewer
from utils.helpers import now_iso


def _artifact_hash(artifact: dict | None) -> str:
    raw = json.dumps(
        artifact or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

DEFAULT_RC_PATH = Path("data/state/release_candidates.json")
DEFAULT_CHANNEL_REVIEW_LOG = Path("data/state/channel_review_log.jsonl")


class ReleaseCandidateStatus(str, Enum):
    DRAFT = "DRAFT"
    GATE_PASSED = "GATE_PASSED"
    EDITORIAL_APPROVED = "EDITORIAL_APPROVED"
    RENDERED = "RENDERED"
    CHANNEL_CHECK_PASSED = "CHANNEL_CHECK_PASSED"
    READY_FOR_CHANNEL_REVIEW = "READY_FOR_CHANNEL_REVIEW"
    READY_FOR_PUBLISH = "READY_FOR_PUBLISH"  # future only
    REJECTED = "REJECTED"


class ChannelReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_EDIT = "NEEDS_EDIT"


@dataclass
class ReleaseCandidate:
    release_candidate_id: str
    content_id: str
    content_type: str
    slug: str
    revision: str = "1"
    status: ReleaseCandidateStatus = ReleaseCandidateStatus.DRAFT
    research_provenance: dict = field(default_factory=dict)
    claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    gate_result: dict = field(default_factory=dict)
    gate_version: str = ""
    editorial_reviewer: str = ""
    editorial_reviewed_at: str = ""
    website_artifact: dict = field(default_factory=dict)
    wechat_artifact: dict = field(default_factory=dict)
    content_fingerprint: str = ""
    channel_consistency_result: dict = field(default_factory=dict)
    website_review: dict = field(default_factory=dict)
    wechat_review: dict = field(default_factory=dict)
    wechat: dict = field(default_factory=dict)
    website: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "release_candidate_id": self.release_candidate_id,
            "content_id": self.content_id,
            "content_type": self.content_type,
            "slug": self.slug,
            "revision": self.revision,
            "status": self.status.value,
            "research_provenance": dict(self.research_provenance),
            "claim_ids": list(self.claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "gate_result": dict(self.gate_result),
            "gate_version": self.gate_version,
            "editorial_reviewer": self.editorial_reviewer,
            "editorial_reviewed_at": self.editorial_reviewed_at,
            "website_artifact": dict(self.website_artifact),
            "wechat_artifact": dict(self.wechat_artifact),
            "content_fingerprint": self.content_fingerprint,
            "channel_consistency_result": dict(self.channel_consistency_result),
            "website_review": dict(self.website_review),
            "wechat_review": dict(self.wechat_review),
            "wechat": dict(self.wechat),
            "website": dict(self.website),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ReleaseCandidate:
        return cls(
            release_candidate_id=str(data.get("release_candidate_id") or ""),
            content_id=str(data.get("content_id") or ""),
            content_type=str(data.get("content_type") or ""),
            slug=str(data.get("slug") or ""),
            revision=str(data.get("revision") or "1"),
            status=ReleaseCandidateStatus(
                data.get("status") or ReleaseCandidateStatus.DRAFT.value
            ),
            research_provenance=dict(data.get("research_provenance") or {}),
            claim_ids=list(data.get("claim_ids") or []),
            evidence_ids=list(data.get("evidence_ids") or []),
            gate_result=dict(data.get("gate_result") or {}),
            gate_version=str(data.get("gate_version") or ""),
            editorial_reviewer=str(data.get("editorial_reviewer") or ""),
            editorial_reviewed_at=str(data.get("editorial_reviewed_at") or ""),
            website_artifact=dict(data.get("website_artifact") or {}),
            wechat_artifact=dict(data.get("wechat_artifact") or {}),
            content_fingerprint=str(data.get("content_fingerprint") or ""),
            channel_consistency_result=dict(data.get("channel_consistency_result") or {}),
            website_review=dict(data.get("website_review") or {}),
            wechat_review=dict(data.get("wechat_review") or {}),
            wechat=dict(data.get("wechat") or {}),
            website=dict(data.get("website") or {}),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


class ReleaseCandidateError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def make_release_candidate_id(content_id: str, revision: str = "1") -> str:
    digest = hashlib.sha256(f"{content_id}|{revision}".encode()).hexdigest()[:16]
    return f"rc-{digest}"


def build_release_candidate(
    candidate: ContentCandidate,
    *,
    revision: str = "1",
    run_consistency: bool = True,
) -> ReleaseCandidate:
    gate = candidate.gate_result or {}
    if not gate.get("passed"):
        raise ReleaseCandidateError("GATE_NOT_PASS", "Hard Gate must PASS")
    if candidate.editorial_status is not EditorialStatus.APPROVED:
        raise ReleaseCandidateError(
            "EDITORIAL_NOT_APPROVED",
            "Editorial must be APPROVED",
        )
    website = candidate.metadata.get("website_artifact") or {}
    wechat = candidate.metadata.get("wechat_artifact") or {}
    if not website or not wechat:
        raise ReleaseCandidateError(
            "NOT_RENDERED",
            "Website and WeChat preview artifacts required",
        )

    consistency = (
        check_channel_consistency(candidate)
        if run_consistency
        else None
    )
    consistency_dict = (
        consistency.to_dict()
        if consistency is not None
        else dict(candidate.metadata.get("channel_consistency_report") or {})
    )
    if not consistency_dict.get("passed"):
        raise ReleaseCandidateError(
            "CHANNEL_CONSISTENCY_FAIL",
            "Channel consistency must PASS before Release Candidate",
        )

    now = now_iso()
    rc = ReleaseCandidate(
        release_candidate_id=make_release_candidate_id(candidate.content_id, revision),
        content_id=candidate.content_id,
        content_type=candidate.content_type.value,
        slug=candidate.slug,
        revision=revision,
        status=ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW,
        research_provenance={
            "knowledge_ids": list(candidate.knowledge_ids),
            "claim_ids": list(candidate.claim_ids),
            "evidence_ids": list(candidate.evidence_ids),
            "source_document_ids": list(candidate.source_document_ids),
        },
        claim_ids=list(candidate.claim_ids),
        evidence_ids=list(candidate.evidence_ids),
        gate_result=dict(gate),
        gate_version=str(gate.get("gate_version") or ""),
        editorial_reviewer=str(candidate.metadata.get("editorial_reviewer") or ""),
        editorial_reviewed_at=str(candidate.metadata.get("editorial_reviewed_at") or ""),
        website_artifact=dict(website),
        wechat_artifact=dict(wechat),
        content_fingerprint=str(
            candidate.metadata.get("content_fingerprint")
            or website.get("content_fingerprint")
            or ""
        ),
        channel_consistency_result=consistency_dict,
        website_review={
            "status": ChannelReviewStatus.PENDING.value,
            "reviewer": "",
            "reviewed_at": "",
        },
        wechat_review={
            "status": ChannelReviewStatus.PENDING.value,
            "reviewer": "",
            "reviewed_at": "",
        },
        wechat={"rendered": True, "reviewed": False, "published": False},
        website={"rendered": True, "reviewed": False, "published": False},
        created_at=now,
        updated_at=now,
    )
    candidate.metadata["release_candidate"] = rc.to_dict()
    candidate.package = {
        **(candidate.package or {}),
        "release_candidate_id": rc.release_candidate_id,
        "status": rc.status.value,
        "wechat_published": False,
        "website_published": False,
        "note": "STOP BEFORE PUBLISH — READY_FOR_CHANNEL_REVIEW only",
    }
    return rc


def assert_ready_for_publish(rc: ReleaseCandidate | dict) -> None:
    """Publisher precondition — reject unless READY_FOR_PUBLISH and both channels approved."""
    data = rc.to_dict() if isinstance(rc, ReleaseCandidate) else rc
    status = data.get("status")
    gate = data.get("gate_result") or {}
    if gate and gate.get("passed") is False:
        raise ReleaseCandidateError("GATE_NOT_PASSED", "Hard Gate must PASS")
    if status == ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW.value:
        raise ReleaseCandidateError(
            "CHANNEL_REVIEW_REQUIRED",
            f"Publisher requires READY_FOR_PUBLISH; current status={status}",
        )
    if status != ReleaseCandidateStatus.READY_FOR_PUBLISH.value:
        # Distinguish editorial vs channel when possible.
        if status in {
            ReleaseCandidateStatus.DRAFT.value,
            ReleaseCandidateStatus.GATE_PASSED.value,
            ReleaseCandidateStatus.EDITORIAL_APPROVED.value,
            ReleaseCandidateStatus.RENDERED.value,
            ReleaseCandidateStatus.CHANNEL_CHECK_PASSED.value,
        }:
            raise ReleaseCandidateError(
                "EDITORIAL_REVIEW_REQUIRED"
                if status
                in {
                    ReleaseCandidateStatus.DRAFT.value,
                    ReleaseCandidateStatus.GATE_PASSED.value,
                }
                else "CHANNEL_REVIEW_REQUIRED",
                f"Publisher requires READY_FOR_PUBLISH; current status={status}",
            )
        raise ReleaseCandidateError(
            "CHANNEL_REVIEW_REQUIRED",
            f"Publisher requires READY_FOR_PUBLISH; current status={status}",
        )
    consistency = data.get("channel_consistency_result") or {}
    if consistency and consistency.get("passed") is False:
        raise ReleaseCandidateError(
            "CHANNEL_CONSISTENCY_FAILED",
            "Channel consistency must PASS before publish",
        )
    website_ok = (data.get("website_review") or {}).get("status") == ChannelReviewStatus.APPROVED.value
    wechat_ok = (data.get("wechat_review") or {}).get("status") == ChannelReviewStatus.APPROVED.value
    if not (website_ok and wechat_ok):
        raise ReleaseCandidateError(
            "CHANNEL_REVIEW_REQUIRED",
            "Both website_review and wechat_review must be APPROVED",
        )


def check_channel_review_preconditions(
    rc: ReleaseCandidate,
    channel: str,
) -> list[str]:
    """Return precondition failure codes (empty = ok)."""
    codes: list[str] = []
    if channel == "website":
        artifact = rc.website_artifact or {}
        if not artifact:
            codes.append("WEBSITE_ARTIFACT_MISSING")
        if artifact.get("published") is True:
            codes.append("ARTIFACT_ALREADY_PUBLISHED")
        if not artifact.get("content_fingerprint") and not rc.content_fingerprint:
            codes.append("FINGERPRINT_MISSING")
        if rc.content_type == "insight":
            route = artifact.get("route") or ""
            if route.startswith("/daily/"):
                codes.append("CONTENT_TYPE_MISMATCH")
            if rc.slug and route and route != f"/insight/{rc.slug}":
                codes.append("SLUG_ROUTE_MISMATCH")
        media = artifact.get("media") or []
        for item in media:
            if isinstance(item, dict) and str(item.get("status") or "").lower() not in {
                "",
                "approved",
            }:
                codes.append("MEDIA_NOT_APPROVED")
                break
    elif channel == "wechat":
        artifact = rc.wechat_artifact or {}
        if not artifact:
            codes.append("WECHAT_ARTIFACT_MISSING")
        if not artifact.get("content_fingerprint") and not rc.content_fingerprint:
            codes.append("FINGERPRINT_MISSING")
        media = artifact.get("media") or []
        for item in media:
            if isinstance(item, dict) and str(item.get("status") or "").lower() not in {
                "",
                "approved",
            }:
                codes.append("MEDIA_NOT_APPROVED")
                break
    else:
        codes.append("UNKNOWN_CHANNEL")

    consistency = rc.channel_consistency_result or {}
    if consistency and consistency.get("passed") is False:
        codes.append("CHANNEL_CONSISTENCY_FAILED")
    if not (rc.content_fingerprint or "").strip():
        if "FINGERPRINT_MISSING" not in codes:
            codes.append("FINGERPRINT_MISSING")
    if not (rc.slug or "").strip():
        codes.append("SLUG_MISSING")
    if not (rc.content_type or "").strip():
        codes.append("CONTENT_TYPE_MISSING")
    return codes


def set_channel_review(
    rc: ReleaseCandidate,
    channel: str,
    status: ChannelReviewStatus,
    *,
    reviewer: str | None = None,
    reason: str = "",
    log_path: str | Path | None = None,
    skip_preconditions: bool = False,
) -> ReleaseCandidate:
    reviewer_name = resolve_reviewer(reviewer)
    old_status = (
        (rc.website_review or {}).get("status")
        if channel == "website"
        else (rc.wechat_review or {}).get("status")
        if channel == "wechat"
        else ""
    )
    if status is ChannelReviewStatus.APPROVED and not skip_preconditions:
        failures = check_channel_review_preconditions(rc, channel)
        if failures:
            raise ReleaseCandidateError(
                "CHANNEL_REVIEW_PRECONDITION_FAILED",
                f"Cannot APPROVE {channel}: {', '.join(failures)}",
            )

    now = now_iso()
    artifact = rc.website_artifact if channel == "website" else rc.wechat_artifact
    artifact_hash = _artifact_hash(artifact)
    entry = {
        "status": status.value,
        "reviewer": reviewer_name,
        "reviewed_at": now,
        "reason": reason,
        "artifact_hash": artifact_hash,
        "content_fingerprint": rc.content_fingerprint,
    }
    if channel == "website":
        rc.website_review = entry
        rc.website["reviewed"] = status is ChannelReviewStatus.APPROVED
    elif channel == "wechat":
        rc.wechat_review = entry
        rc.wechat["reviewed"] = status is ChannelReviewStatus.APPROVED
    else:
        raise ReleaseCandidateError("UNKNOWN_CHANNEL", f"Unknown channel: {channel}")

    website_ok = rc.website_review.get("status") == ChannelReviewStatus.APPROVED.value
    wechat_ok = rc.wechat_review.get("status") == ChannelReviewStatus.APPROVED.value
    if website_ok and wechat_ok:
        # Require prior gate/consistency still true.
        if (rc.channel_consistency_result or {}).get("passed") is False:
            raise ReleaseCandidateError(
                "CHANNEL_CONSISTENCY_FAILED",
                "Cannot reach READY_FOR_PUBLISH with failed consistency",
            )
        if (rc.gate_result or {}).get("passed") is False:
            raise ReleaseCandidateError("GATE_NOT_PASSED", "Cannot READY_FOR_PUBLISH with gate fail")
        rc.status = ReleaseCandidateStatus.READY_FOR_PUBLISH
    elif status is ChannelReviewStatus.REJECTED:
        rc.status = ReleaseCandidateStatus.REJECTED
    elif rc.status is ReleaseCandidateStatus.READY_FOR_PUBLISH:
        # Losing an approval should drop back.
        rc.status = ReleaseCandidateStatus.READY_FOR_CHANNEL_REVIEW
    rc.updated_at = now

    review_id = hashlib.sha256(
        f"{rc.release_candidate_id}|{channel}|{now}|{status.value}".encode()
    ).hexdigest()[:16]
    target = Path(log_path) if log_path else DEFAULT_CHANNEL_REVIEW_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "review_id": review_id,
                    "release_candidate_id": rc.release_candidate_id,
                    "content_id": rc.content_id,
                    "channel": channel,
                    "old_status": old_status or ChannelReviewStatus.PENDING.value,
                    "new_status": status.value,
                    "reviewer": reviewer_name,
                    "reviewed_at": now,
                    "reason": reason,
                    "artifact_hash": artifact_hash,
                    "content_fingerprint": rc.content_fingerprint,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return rc


class ReleaseCandidateStore:
    def __init__(self, path: str | Path | None = None) -> None:
        cfg = load_content_config()
        default = (cfg.get("paths") or {}).get("release_candidates") or str(DEFAULT_RC_PATH)
        self.path = Path(path) if path else Path(default)
        self._by_id: dict[str, ReleaseCandidate] = {}

    def upsert(self, rc: ReleaseCandidate) -> ReleaseCandidate:
        self._by_id[rc.release_candidate_id] = rc
        return rc

    def get(self, rc_id: str) -> ReleaseCandidate | None:
        return self._by_id.get(rc_id)

    def get_by_content_id(self, content_id: str) -> ReleaseCandidate | None:
        for rc in self._by_id.values():
            if rc.content_id == content_id:
                return rc
        return None

    def all(self) -> list[ReleaseCandidate]:
        return list(self._by_id.values())

    def load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        rows = payload.get("release_candidates") if isinstance(payload, dict) else payload
        count = 0
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            rc = ReleaseCandidate.from_dict(row)
            if rc.release_candidate_id:
                self._by_id[rc.release_candidate_id] = rc
                count += 1
        return count

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": now_iso(),
            "release_candidates": [rc.to_dict() for rc in self.all()],
        }
        fd, tmp_name = tempfile.mkstemp(
            prefix="release_candidates_", suffix=".json", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @classmethod
    def load_or_create(cls, path: str | Path | None = None) -> ReleaseCandidateStore:
        store = cls(path=path)
        store.load()
        return store
