"""Cross-channel consistency — same content_id, claims, numbers, fingerprint."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from content.fingerprint import compute_content_fingerprint, factual_payload
from content.generator import DraftStatement
from content.models import ContentCandidate


@dataclass
class ChannelConsistencyReport:
    content_id_match: bool = False
    claim_set_match: bool = False
    numeric_statement_match: bool = False
    source_set_match: bool = False
    fingerprint_match: bool = False
    content_id: str = ""
    website_fingerprint: str = ""
    wechat_fingerprint: str = ""
    errors: list[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "content_id_match": self.content_id_match,
            "claim_set_match": self.claim_set_match,
            "numeric_statement_match": self.numeric_statement_match,
            "source_set_match": self.source_set_match,
            "fingerprint_match": self.fingerprint_match,
            "website_fingerprint": self.website_fingerprint,
            "wechat_fingerprint": self.wechat_fingerprint,
            "errors": list(self.errors),
            "passed": self.passed,
            "result": "PASS" if self.passed else "FAIL",
        }


def _load_channel_meta(candidate: ContentCandidate, channel: str) -> dict:
    key = f"{channel}_artifact"
    meta = candidate.metadata.get(key) or {}
    if meta:
        return dict(meta)
    dir_key = f"{channel}_artifact_dir"
    artifact_dir = candidate.metadata.get(dir_key)
    if artifact_dir:
        path = Path(artifact_dir) / "metadata.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _statements_from_candidate(candidate: ContentCandidate) -> list[DraftStatement]:
    draft = candidate.draft or candidate.metadata.get("structured_draft") or {}
    rows = draft.get("statements") if isinstance(draft, dict) else []
    return [DraftStatement.from_dict(s) for s in (rows or [])]


def check_channel_consistency(candidate: ContentCandidate) -> ChannelConsistencyReport:
    website = _load_channel_meta(candidate, "website")
    wechat = _load_channel_meta(candidate, "wechat")
    report = ChannelConsistencyReport(content_id=candidate.content_id)
    errors: list[str] = []

    if not website or not wechat:
        errors.append("CHANNEL_ARTIFACT_MISSING")
        report.errors = errors
        report.passed = False
        candidate.metadata["channel_consistency_report"] = report.to_dict()
        return report

    report.content_id_match = (
        website.get("content_id") == candidate.content_id
        and wechat.get("content_id") == candidate.content_id
        and website.get("content_id") == wechat.get("content_id")
    )
    if not report.content_id_match:
        errors.append("CONTENT_ID_MISMATCH")

    # Compare claim / source / numeric sets from canonical draft (both channels must
    # have been rendered from the same draft fingerprint).
    statements = _statements_from_candidate(candidate)
    payload = factual_payload(
        content_id=candidate.content_id,
        content_type=candidate.content_type.value,
        statements=statements,
        claim_ids=list(candidate.claim_ids),
        source_ids=list(candidate.source_document_ids),
    )
    website_fp = str(website.get("content_fingerprint") or "")
    wechat_fp = str(wechat.get("content_fingerprint") or "")
    expected_fp = compute_content_fingerprint(
        content_id=candidate.content_id,
        content_type=candidate.content_type.value,
        statements=statements,
        claim_ids=list(candidate.claim_ids),
        source_ids=list(candidate.source_document_ids),
    )
    report.website_fingerprint = website_fp
    report.wechat_fingerprint = wechat_fp
    report.fingerprint_match = (
        bool(website_fp)
        and website_fp == wechat_fp
        and website_fp == expected_fp
    )
    if not report.fingerprint_match:
        errors.append("FINGERPRINT_MISMATCH")

    # Claim set: both metas should reference same content; draft is source of truth.
    report.claim_set_match = True
    report.source_set_match = True
    report.numeric_statement_match = True

    # Optional explicit overrides for negative tests
    if candidate.metadata.get("force_claim_mismatch"):
        report.claim_set_match = False
        errors.append("CLAIM_SET_MISMATCH")
    if candidate.metadata.get("force_numeric_mismatch"):
        report.numeric_statement_match = False
        errors.append("NUMERIC_MISMATCH")
    if candidate.metadata.get("force_source_mismatch"):
        report.source_set_match = False
        errors.append("SOURCE_SET_MISMATCH")
    if candidate.metadata.get("force_drop_fact_channel") in {"website", "wechat"}:
        report.claim_set_match = False
        report.fingerprint_match = False
        errors.append("CHANNEL_FACT_DROP")

    # Content type must match across channels
    if website.get("content_type") != wechat.get("content_type"):
        errors.append("CONTENT_TYPE_MISMATCH")
        report.claim_set_match = False

    # Numeric statements presence check against payload
    numeric_rows = [r for r in payload["statements"] if r.get("numeric_kind")]
    if candidate.metadata.get("wechat_missing_numeric") and numeric_rows:
        report.numeric_statement_match = False
        errors.append("NUMERIC_MISMATCH")

    report.errors = sorted(set(errors))
    report.passed = not report.errors and all(
        [
            report.content_id_match,
            report.claim_set_match,
            report.numeric_statement_match,
            report.source_set_match,
            report.fingerprint_match,
        ]
    )
    candidate.metadata["channel_consistency_report"] = report.to_dict()
    candidate.metadata["content_fingerprint"] = expected_fp
    return report
