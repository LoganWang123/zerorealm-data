"""Export human-verified claims for downstream Knowledge/Content (not Publish)."""

from __future__ import annotations

import json
from pathlib import Path

from research.atom_store import DEFAULT_ATOMS_PATH, ResearchAtomStore
from research.models import ClaimStatus
from utils.helpers import now_iso

DEFAULT_EXPORT_PATH = Path("data/research/verified_claims.json")


def export_verified_research(
    *,
    store: ResearchAtomStore | None = None,
    atoms_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    """Write verified-only research artifact. Excludes draft/rejected and snippets."""
    atom_store = store or ResearchAtomStore.load_or_create(atoms_path or DEFAULT_ATOMS_PATH)
    rows: list[dict] = []
    for claim in atom_store.list_verified_claims():
        if claim.status is not ClaimStatus.VERIFIED:
            continue
        sources = [atom_store.sources[sid] for sid in claim.source_ids if sid in atom_store.sources]
        lineage = atom_store.lineage.get(claim.id) or {}
        rows.append(
            {
                "claim_id": claim.id,
                "claim_text": claim.text,
                "claim_status": claim.status.value,
                "claim_type": claim.type.value,
                "verified_at": claim.reviewed_at,
                "reviewer_note": claim.review_note,
                "evidence_ids": list(claim.evidence_ids),
                "source_document_ids": list(claim.source_ids),
                "canonical_source_urls": [s.url for s in sources if s.url],
                "publishers": [s.source_name for s in sources if s.source_name],
                "published_at": [s.published_at for s in sources],
                "source_types": [s.source_type for s in sources],
                "source_tiers": [
                    (lineage.get("source_tier") or "")
                ],
                "discovery": {
                    "provider": lineage.get("discovery_provider")
                    or (sources[0].discovery_provider if sources else ""),
                    "query": lineage.get("discovery_query")
                    or (sources[0].discovery_query if sources else ""),
                    "candidate_id": lineage.get("candidate_id")
                    or (sources[0].discovery_candidate_id if sources else ""),
                    "intake": lineage.get("intake") or (
                        "discovery" if (sources and sources[0].discovery_provider) else "registry"
                    ),
                },
                # Explicitly omit AnySearch snippet / provider_content bodies.
            }
        )

    payload = {
        "version": 1,
        "generated_at": now_iso(),
        "count": len(rows),
        "claims": rows,
        "note": (
            "Verified Research Output only. Does not trigger Daily/Insight/Publish. "
            "Registry and Discovery intakes share this layer."
        ),
    }
    target = Path(output_path) if output_path else DEFAULT_EXPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
