"""Publish-Ready Package builder — STOP before channel publish."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from content.models import ContentCandidate, EditorialStatus
from utils.helpers import now_iso

DEFAULT_PACKAGES_PATH = Path("data/state/publish_ready_packages.json")


class PackageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def build_publish_ready_package(candidate: ContentCandidate) -> dict:
    gate = candidate.gate_result or {}
    if not gate.get("passed"):
        raise PackageError("GATE_NOT_PASS", "Hard Gate must PASS before package")
    if candidate.editorial_status is not EditorialStatus.APPROVED:
        raise PackageError(
            "EDITORIAL_NOT_APPROVED",
            "Editorial status must be APPROVED before package",
        )
    if not candidate.draft:
        raise PackageError("DRAFT_MISSING", "Internal draft required")

    package = {
        "content_id": candidate.content_id,
        "content_type": candidate.content_type.value,
        "slug": candidate.slug,
        "title": candidate.draft.get("title") or candidate.primary_signal,
        "summary": candidate.draft.get("summary") or candidate.research_question,
        "body": candidate.draft.get("body") or "",
        "claim_map": candidate.draft.get("claim_map") or {cid: True for cid in candidate.claim_ids},
        "source_map": candidate.draft.get("source_map")
        or {
            "source_document_ids": list(candidate.source_document_ids),
            "evidence_ids": list(candidate.evidence_ids),
            "independent_source_count": candidate.independent_source_count,
        },
        "editorial_gate_result": gate,
        "gate_version": gate.get("gate_version"),
        "research_review_provenance": {
            "knowledge_ids": list(candidate.knowledge_ids),
            "claim_ids": list(candidate.claim_ids),
        },
        "editorial_reviewer": candidate.metadata.get("editorial_reviewer"),
        "editorial_reviewed_at": candidate.metadata.get("editorial_reviewed_at"),
        "images_metadata": candidate.metadata.get("images_metadata") or {},
        "website_rendering_input": {
            "content_id": candidate.content_id,
            "slug": candidate.slug,
            "content_type": candidate.content_type.value,
        },
        "wechat_rendering_input": {
            "content_id": candidate.content_id,
            "title": candidate.draft.get("title"),
            "content_type": candidate.content_type.value,
        },
        "status": "READY_FOR_CHANNEL_RENDER",
        "wechat_published": False,
        "website_published": False,
        "generated_at": now_iso(),
        "note": "STOP BEFORE PUBLISH — package is intake for channel render / RC only",
    }
    candidate.package = package
    return package


def save_package(
    package: dict,
    *,
    path: str | Path | None = None,
) -> Path:
    target = Path(path) if path else DEFAULT_PACKAGES_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if target.exists():
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            existing = list(payload.get("packages") or [])
        except (OSError, json.JSONDecodeError):
            existing = []
    # Replace same content_id if present
    existing = [p for p in existing if p.get("content_id") != package.get("content_id")]
    existing.append(package)
    out = {"version": 1, "updated_at": now_iso(), "packages": existing}
    fd, tmp_name = tempfile.mkstemp(prefix="packages_", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(out, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target
