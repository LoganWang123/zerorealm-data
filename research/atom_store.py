"""Durable research atoms store (SourceDocument / Evidence / Claim).

Protects human ClaimStatus.VERIFIED from discovery reruns.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from research.models import (
    Claim,
    ClaimStatus,
    ClaimType,
    Confidence,
    Evidence,
    SourceDocument,
)
from utils.helpers import now_iso

DEFAULT_ATOMS_PATH = Path("data/state/research_atoms.json")


def _claim_to_dict(claim: Claim) -> dict:
    return {
        "id": claim.id,
        "text": claim.text,
        "type": claim.type.value,
        "status": claim.status.value,
        "confidence": claim.confidence.value,
        "source_ids": list(claim.source_ids),
        "evidence_ids": list(claim.evidence_ids),
        "based_on_claim_ids": list(claim.based_on_claim_ids),
        "reviewed_at": claim.reviewed_at,
        "review_note": claim.review_note,
    }


def _claim_from_dict(data: dict) -> Claim:
    return Claim(
        id=str(data.get("id") or ""),
        text=str(data.get("text") or ""),
        type=ClaimType(data.get("type") or ClaimType.FACT.value),
        status=ClaimStatus(data.get("status") or ClaimStatus.DRAFT.value),
        confidence=Confidence(data.get("confidence") or Confidence.MEDIUM.value),
        source_ids=list(data.get("source_ids") or []),
        evidence_ids=list(data.get("evidence_ids") or []),
        based_on_claim_ids=list(data.get("based_on_claim_ids") or []),
        reviewed_at=data.get("reviewed_at"),
        review_note=str(data.get("review_note") or ""),
    )


def _source_to_dict(source: SourceDocument) -> dict:
    return asdict(source)


def _source_from_dict(data: dict) -> SourceDocument:
    return SourceDocument(
        id=str(data.get("id") or ""),
        url=str(data.get("url") or ""),
        title=str(data.get("title") or ""),
        source_name=str(data.get("source_name") or ""),
        published_at=data.get("published_at"),
        fetched_at=str(data.get("fetched_at") or ""),
        raw_excerpt=str(data.get("raw_excerpt") or ""),
        credibility=str(data.get("credibility") or "medium"),
        accessed_at=str(data.get("accessed_at") or ""),
        source_type=str(data.get("source_type") or "web"),
        discovery_provider=str(data.get("discovery_provider") or ""),
        discovery_query=str(data.get("discovery_query") or ""),
        discovery_candidate_id=str(data.get("discovery_candidate_id") or ""),
        discovery_original_url=str(data.get("discovery_original_url") or ""),
    )


def _evidence_to_dict(evidence: Evidence) -> dict:
    return asdict(evidence)


def _evidence_from_dict(data: dict) -> Evidence:
    return Evidence(
        id=str(data.get("id") or ""),
        source_id=str(data.get("source_id") or ""),
        quote=str(data.get("quote") or ""),
        locator=str(data.get("locator") or ""),
    )


class ResearchAtomStore:
    """JSON store for research atoms used by Discovery + Claim Review."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_ATOMS_PATH
        self.sources: dict[str, SourceDocument] = {}
        self.evidence: dict[str, Evidence] = {}
        self.claims: dict[str, Claim] = {}
        self.lineage: dict[str, dict] = {}  # claim_id → lineage metadata

    def upsert_atoms(
        self,
        *,
        source: SourceDocument,
        evidence: list[Evidence],
        claims: list[Claim],
        lineage: dict | None = None,
    ) -> None:
        """Upsert atoms; never downgrade/overwrite human VERIFIED/REJECTED claims."""
        existing_source = self.sources.get(source.id)
        if existing_source is not None and existing_source.raw_excerpt != source.raw_excerpt:
            # New source version — keep old source, mark review needed on verified claims.
            for claim in self.claims.values():
                if source.id in claim.source_ids and claim.status is ClaimStatus.VERIFIED:
                    note = claim.review_note or ""
                    marker = "[SOURCE_UPDATED_REVIEW_NEEDED]"
                    if marker not in note:
                        claim.review_note = f"{note} {marker}".strip()
            # Store updated excerpt under metadata lineage only; keep verified evidence quote.
            source = SourceDocument(
                id=source.id,
                url=source.url or existing_source.url,
                title=source.title or existing_source.title,
                source_name=source.source_name or existing_source.source_name,
                published_at=source.published_at or existing_source.published_at,
                fetched_at=source.fetched_at or existing_source.fetched_at,
                raw_excerpt=existing_source.raw_excerpt,
                credibility=source.credibility or existing_source.credibility,
                accessed_at=source.accessed_at or existing_source.accessed_at,
                source_type=source.source_type or existing_source.source_type,
                discovery_provider=source.discovery_provider or existing_source.discovery_provider,
                discovery_query=source.discovery_query or existing_source.discovery_query,
                discovery_candidate_id=(
                    source.discovery_candidate_id or existing_source.discovery_candidate_id
                ),
                discovery_original_url=(
                    source.discovery_original_url or existing_source.discovery_original_url
                ),
            )
            self.lineage.setdefault(source.id, {})
            self.lineage[source.id]["source_update_warning"] = "SOURCE_UPDATED_REVIEW_NEEDED"
            self.lineage[source.id]["updated_excerpt_preview"] = (source.raw_excerpt or "")[:120]

        self.sources[source.id] = source
        for item in evidence:
            self.evidence[item.id] = item
        for claim in claims:
            existing = self.claims.get(claim.id)
            if existing is not None and existing.status in {
                ClaimStatus.VERIFIED,
                ClaimStatus.REJECTED,
            }:
                # Preserve human decision; refresh text/links only if empty.
                if not existing.source_ids:
                    existing.source_ids = list(claim.source_ids)
                if not existing.evidence_ids:
                    existing.evidence_ids = list(claim.evidence_ids)
                self.claims[existing.id] = existing
            else:
                self.claims[claim.id] = claim
            if lineage:
                self.lineage[claim.id] = {
                    **(self.lineage.get(claim.id) or {}),
                    **lineage,
                }

    def get_claim(self, claim_id: str) -> Claim | None:
        return self.claims.get(claim_id)

    def list_verified_claims(self) -> list[Claim]:
        return [c for c in self.claims.values() if c.status is ClaimStatus.VERIFIED]

    def load(self, path: str | Path | None = None) -> int:
        target = Path(path) if path else self.path
        self.path = target
        if not target.exists():
            return 0
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        for row in payload.get("sources") or []:
            if isinstance(row, dict) and row.get("id"):
                self.sources[row["id"]] = _source_from_dict(row)
        for row in payload.get("evidence") or []:
            if isinstance(row, dict) and row.get("id"):
                self.evidence[row["id"]] = _evidence_from_dict(row)
        for row in payload.get("claims") or []:
            if isinstance(row, dict) and row.get("id"):
                self.claims[row["id"]] = _claim_from_dict(row)
        lineage = payload.get("lineage") or {}
        if isinstance(lineage, dict):
            self.lineage = {str(k): dict(v) for k, v in lineage.items() if isinstance(v, dict)}
        return len(self.claims)

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": now_iso(),
            "sources": [_source_to_dict(s) for s in self.sources.values()],
            "evidence": [_evidence_to_dict(e) for e in self.evidence.values()],
            "claims": [_claim_to_dict(c) for c in self.claims.values()],
            "lineage": self.lineage,
        }
        fd, tmp_name = tempfile.mkstemp(
            prefix="research_atoms_", suffix=".json", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @classmethod
    def load_or_create(cls, path: str | Path | None = None) -> ResearchAtomStore:
        store = cls(path=path)
        store.load()
        return store
