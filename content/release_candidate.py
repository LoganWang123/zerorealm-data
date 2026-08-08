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
    """Future publisher precondition — this round must reject CHANNEL_REVIEW_REQUIRED."""
    data = rc.to_dict() if isinstance(rc, ReleaseCandidate) else rc
    status = data.get("status")
    if status != ReleaseCandidateStatus.READY_FOR_PUBLISH.value:
        raise ReleaseCandidateError(
            "CHANNEL_REVIEW_REQUIRED",
            f"Publisher requires READY_FOR_PUBLISH; current status={status}",
        )
    website_ok = (data.get("website_review") or {}).get("status") == ChannelReviewStatus.APPROVED.value
    wechat_ok = (data.get("wechat_review") or {}).get("status") == ChannelReviewStatus.APPROVED.value
    if not (website_ok and wechat_ok):
        raise ReleaseCandidateError(
            "CHANNEL_REVIEW_REQUIRED",
            "Both website_review and wechat_review must be APPROVED",
        )


def set_channel_review(
    rc: ReleaseCandidate,
    channel: str,
    status: ChannelReviewStatus,
    *,
    reviewer: str | None = None,
    reason: str = "",
    log_path: str | Path | None = None,
) -> ReleaseCandidate:
    reviewer_name = resolve_reviewer(reviewer)
    now = now_iso()
    entry = {
        "status": status.value,
        "reviewer": reviewer_name,
        "reviewed_at": now,
        "reason": reason,
    }
    if channel == "website":
        rc.website_review = entry
        rc.website["reviewed"] = status is ChannelReviewStatus.APPROVED
    elif channel == "wechat":
        rc.wechat_review = entry
        rc.wechat["reviewed"] = status is ChannelReviewStatus.APPROVED
    else:
        raise ReleaseCandidateError("UNKNOWN_CHANNEL", f"Unknown channel: {channel}")

    # Advance to READY_FOR_PUBLISH only when both approved — allowed for fixture tests,
    # but production smoke should stop at READY_FOR_CHANNEL_REVIEW.
    website_ok = rc.website_review.get("status") == ChannelReviewStatus.APPROVED.value
    wechat_ok = rc.wechat_review.get("status") == ChannelReviewStatus.APPROVED.value
    if website_ok and wechat_ok:
        rc.status = ReleaseCandidateStatus.READY_FOR_PUBLISH
    elif status is ChannelReviewStatus.REJECTED:
        rc.status = ReleaseCandidateStatus.REJECTED
    rc.updated_at = now

    target = Path(log_path) if log_path else DEFAULT_CHANNEL_REVIEW_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "release_candidate_id": rc.release_candidate_id,
                    "content_id": rc.content_id,
                    "channel": channel,
                    "status": status.value,
                    "reviewer": reviewer_name,
                    "reviewed_at": now,
                    "reason": reason,
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
