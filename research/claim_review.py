"""Human Claim Review — explicit ClaimStatus transitions with audit trail.

Queue APPROVED ≠ ClaimStatus.VERIFIED.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from research.atom_store import ResearchAtomStore
from research.models import Claim, ClaimStatus, SourceDocument
from research.validators import has_blocking_issues, validate_discovery_atoms
from utils.helpers import now_iso

DEFAULT_REVIEW_LOG_PATH = Path("data/state/research_review_log.jsonl")
FORBIDDEN_REVIEWERS = frozenset(
    {"", "ai", "system", "bot", "auto", "automated", "cursor"}
)


class ClaimReviewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def resolve_reviewer(explicit: str | None = None) -> str:
    name = (explicit or os.getenv("ZEROREALM_REVIEWER") or "").strip()
    if not name or name.lower() in FORBIDDEN_REVIEWERS:
        raise ClaimReviewError(
            "REVIEWER_REQUIRED",
            "Explicit human reviewer required (--reviewer or ZEROREALM_REVIEWER)",
        )
    return name


def _is_snippet_only(source: SourceDocument, claim: Claim, evidence_quotes: list[str]) -> bool:
    source_type = (source.source_type or "").strip().lower()
    if source_type in {"search_snippet", "provider_content", "anysearch_snippet"}:
        return True
    if not (source.url or "").strip():
        return True
    # Evidence quote equals discovery snippet markers only
    for quote in evidence_quotes:
        q = (quote or "").strip()
        if q.startswith("provider ") or "不可作证据" in q:
            return True
    return False


def check_verify_preconditions(
    claim: Claim,
    store: ResearchAtomStore,
) -> list[str]:
    """Return precondition failure codes (empty = ok)."""
    codes: list[str] = []
    if not claim.evidence_ids:
        codes.append("CLAIM_MISSING_EVIDENCE")
    if not claim.source_ids:
        codes.append("CLAIM_MISSING_SOURCE")

    sources: dict[str, SourceDocument] = {}
    for sid in claim.source_ids:
        source = store.sources.get(sid)
        if source is None:
            codes.append("SOURCE_DOCUMENT_MISSING")
            continue
        sources[sid] = source
        if not (source.url or "").strip():
            codes.append("SOURCE_MISSING_URL")
        quotes = [
            store.evidence[eid].quote
            for eid in claim.evidence_ids
            if eid in store.evidence
        ]
        if _is_snippet_only(source, claim, quotes):
            codes.append("SEARCH_SNIPPET_AS_EVIDENCE")

    for eid in claim.evidence_ids:
        if eid not in store.evidence:
            codes.append("EVIDENCE_MISSING")

    issues = validate_discovery_atoms([claim], sources)
    if has_blocking_issues(issues):
        codes.append("RESEARCH_VALIDATORS_FAILED")
        codes.extend(sorted({i.code for i in issues if i.severity == "error"}))

    # Deduplicate while preserving order
    return list(dict.fromkeys(codes))


def append_review_log(
    entry: dict,
    *,
    path: str | Path | None = None,
) -> None:
    target = Path(path) if path else DEFAULT_REVIEW_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def set_claim_status(
    store: ResearchAtomStore,
    claim_id: str,
    new_status: ClaimStatus,
    *,
    reviewer: str | None = None,
    reason: str = "",
    log_path: str | Path | None = None,
    persist: bool = True,
) -> Claim:
    """Explicit human claim status transition with append-only audit log."""
    claim = store.get_claim(claim_id)
    if claim is None:
        raise ClaimReviewError("CLAIM_NOT_FOUND", f"Unknown claim_id: {claim_id}")

    reviewer_name = resolve_reviewer(reviewer)
    old_status = claim.status

    if new_status is ClaimStatus.VERIFIED:
        failures = check_verify_preconditions(claim, store)
        if failures:
            raise ClaimReviewError(
                "CLAIM_VERIFY_PRECONDITION_FAILED",
                ", ".join(failures),
            )

    if new_status not in {ClaimStatus.VERIFIED, ClaimStatus.REJECTED, ClaimStatus.DRAFT}:
        raise ClaimReviewError("INVALID_CLAIM_STATUS", f"Unsupported status: {new_status}")

    claim.status = new_status
    claim.reviewed_at = now_iso()
    claim.review_note = reason or claim.review_note
    store.claims[claim.id] = claim

    review_id = f"rev-{claim.id}-{claim.reviewed_at}"
    entry = {
        "review_id": review_id,
        "claim_id": claim.id,
        "old_status": old_status.value,
        "new_status": new_status.value,
        "reviewer": reviewer_name,
        "reviewed_at": claim.reviewed_at,
        "reason": reason,
        "evidence_ids": list(claim.evidence_ids),
        "source_document_ids": list(claim.source_ids),
    }
    append_review_log(entry, path=log_path)
    if persist:
        store.save()
    return claim


def claim_review_payload(store: ResearchAtomStore, claim_id: str) -> dict:
    claim = store.get_claim(claim_id)
    if claim is None:
        raise ClaimReviewError("CLAIM_NOT_FOUND", f"Unknown claim_id: {claim_id}")
    sources = [store.sources[sid] for sid in claim.source_ids if sid in store.sources]
    evidence = [store.evidence[eid] for eid in claim.evidence_ids if eid in store.evidence]
    lineage = store.lineage.get(claim.id) or {}
    return {
        "claim_id": claim.id,
        "text": claim.text,
        "type": claim.type.value,
        "status": claim.status.value,
        "reviewed_at": claim.reviewed_at,
        "review_note": claim.review_note,
        "evidence": [
            {"id": e.id, "source_id": e.source_id, "quote": e.quote[:500]} for e in evidence
        ],
        "sources": [
            {
                "id": s.id,
                "url": s.url,
                "title": s.title,
                "publisher": s.source_name,
                "published_at": s.published_at,
                "source_type": s.source_type,
                "discovery_provider": s.discovery_provider,
                "discovery_query": s.discovery_query,
                "discovery_candidate_id": s.discovery_candidate_id,
            }
            for s in sources
        ],
        "lineage": lineage,
        "preconditions": check_verify_preconditions(claim, store),
    }
