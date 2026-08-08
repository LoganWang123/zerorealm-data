"""Canonical content fingerprint — factual identity independent of channel styling."""

from __future__ import annotations

import hashlib
import json
import re

from content.generator import DraftStatement, StructuredDraft


def extract_statements_from_draft(draft: StructuredDraft | dict) -> list[DraftStatement]:
    if isinstance(draft, StructuredDraft):
        return list(draft.statements)
    return [DraftStatement.from_dict(s) for s in (draft.get("statements") or [])]


def _normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[，。；、！？,.!?;:：\"'“”‘’]", "", t)
    return t


def factual_payload(
    *,
    content_id: str,
    content_type: str,
    statements: list[DraftStatement] | list[dict],
    claim_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> dict:
    rows: list[dict] = []
    for stmt in statements:
        if isinstance(stmt, dict):
            stype = str(stmt.get("statement_type") or stmt.get("kind") or "")
            text = str(stmt.get("text") or "")
            cids = list(stmt.get("claim_ids") or stmt.get("supporting_claim_ids") or [])
            numeric = stmt.get("numeric_kind")
        else:
            stype = stmt.statement_type
            text = stmt.text
            cids = list(stmt.claim_ids or stmt.supporting_claim_ids)
            numeric = stmt.numeric_kind
        if stype not in {"FACT", "EXPERIMENT_PARAMETER", "INFERENCE"}:
            continue
        rows.append(
            {
                "type": stype,
                "text": _normalize_text(text),
                "claim_ids": sorted(cids),
                "numeric_kind": numeric or "",
            }
        )
    rows.sort(key=lambda r: (r["type"], r["text"], ",".join(r["claim_ids"])))
    all_claims = sorted(
        set(claim_ids or []) | {cid for r in rows for cid in r["claim_ids"]}
    )
    return {
        "content_id": content_id,
        "content_type": content_type,
        "statements": rows,
        "claim_ids": all_claims,
        "source_ids": sorted(set(source_ids or [])),
    }


def compute_content_fingerprint(
    *,
    content_id: str,
    content_type: str,
    statements: list | None = None,
    draft: StructuredDraft | dict | None = None,
    claim_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> str:
    if statements is None and draft is not None:
        statements = extract_statements_from_draft(draft)
    payload = factual_payload(
        content_id=content_id,
        content_type=content_type,
        statements=statements or [],
        claim_ids=claim_ids,
        source_ids=source_ids,
    )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
