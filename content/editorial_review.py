"""Human Editorial Review — separate from Research Claim Review."""

from __future__ import annotations

import json
import os
from pathlib import Path

from content.models import ContentCandidate, ContentCandidateStatus, EditorialStatus
from research.claim_review import ClaimReviewError, resolve_reviewer
from utils.helpers import now_iso

DEFAULT_EDITORIAL_LOG = Path("data/state/editorial_review_log.jsonl")


def append_editorial_log(entry: dict, *, path: str | Path | None = None) -> None:
    target = Path(path) if path else DEFAULT_EDITORIAL_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def set_editorial_status(
    candidate: ContentCandidate,
    new_status: EditorialStatus,
    *,
    reviewer: str | None = None,
    reason: str = "",
    log_path: str | Path | None = None,
) -> ContentCandidate:
    """Editorial APPROVED requires Hard Gate PASS; cannot bypass hard errors."""
    reviewer_name = resolve_reviewer(reviewer)
    old = candidate.editorial_status

    if new_status is EditorialStatus.APPROVED:
        gate = candidate.gate_result or {}
        if not gate.get("passed"):
            raise ClaimReviewError(
                "EDITORIAL_APPROVE_REQUIRES_GATE_PASS",
                "Hard Gate must PASS before Editorial APPROVED",
            )
        if candidate.status is ContentCandidateStatus.GATE_FAILED:
            raise ClaimReviewError(
                "EDITORIAL_APPROVE_REQUIRES_GATE_PASS",
                "Candidate status is GATE_FAILED",
            )
        non_bypass = gate.get("non_bypassable_hit") or []
        if non_bypass:
            raise ClaimReviewError(
                "EDITORIAL_CANNOT_BYPASS_HARD_GATE",
                f"Non-bypassable gate errors present: {', '.join(non_bypass)}",
            )

    candidate.editorial_status = new_status
    if new_status is EditorialStatus.REJECTED:
        candidate.status = ContentCandidateStatus.REJECTED
    elif new_status is EditorialStatus.APPROVED:
        candidate.status = ContentCandidateStatus.READY_FOR_CHANNEL_RENDER
    reviewed_at = now_iso()
    candidate.metadata["editorial_reviewer"] = reviewer_name
    candidate.metadata["editorial_reviewed_at"] = reviewed_at
    candidate.metadata["editorial_reason"] = reason
    append_editorial_log(
        {
            "content_candidate_id": candidate.content_candidate_id,
            "draft_id": candidate.content_id,
            "old_status": old.value,
            "new_status": new_status.value,
            "reviewer": reviewer_name,
            "reviewed_at": reviewed_at,
            "reason": reason,
            "gate_version": (candidate.gate_result or {}).get("gate_version"),
            "gate_result": (candidate.gate_result or {}).get("passed"),
        },
        path=log_path or os.getenv("ZEROREALM_EDITORIAL_LOG") or DEFAULT_EDITORIAL_LOG,
    )
    return candidate
