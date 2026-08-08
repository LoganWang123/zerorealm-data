"""Knowledge layer — only ClaimStatus.VERIFIED enters; Evidence remains SoT."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from research.atom_store import DEFAULT_ATOMS_PATH, ResearchAtomStore
from research.models import ClaimStatus
from utils.helpers import now_iso

DEFAULT_KNOWLEDGE_PATH = Path("data/state/knowledge_store.json")


class KnowledgeStatus(str, Enum):
    ACTIVE = "active"
    INVALIDATED = "invalidated"


def make_knowledge_id(claim_id: str) -> str:
    digest = hashlib.sha256(claim_id.encode("utf-8")).hexdigest()[:16]
    return f"kn-{digest}"


@dataclass
class KnowledgeRecord:
    knowledge_id: str
    claim_id: str
    claim_text: str
    claim_type: str
    verified_at: str | None = None
    reviewer: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    source_document_ids: list[str] = field(default_factory=list)
    canonical_urls: list[str] = field(default_factory=list)
    publishers: list[str] = field(default_factory=list)
    published_at: list[str | None] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    source_tiers: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    company_tags: list[str] = field(default_factory=list)
    source_cluster_ids: list[str] = field(default_factory=list)
    independent_source_count: int = 0
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    invalidated_at: str | None = None
    invalidation_reason: str = ""
    lineage: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeRecord:
        return cls(
            knowledge_id=str(data.get("knowledge_id") or ""),
            claim_id=str(data.get("claim_id") or ""),
            claim_text=str(data.get("claim_text") or ""),
            claim_type=str(data.get("claim_type") or ""),
            verified_at=data.get("verified_at"),
            reviewer=str(data.get("reviewer") or ""),
            evidence_ids=list(data.get("evidence_ids") or []),
            source_document_ids=list(data.get("source_document_ids") or []),
            canonical_urls=list(data.get("canonical_urls") or []),
            publishers=list(data.get("publishers") or []),
            published_at=list(data.get("published_at") or []),
            source_types=list(data.get("source_types") or []),
            source_tiers=list(data.get("source_tiers") or []),
            topic_tags=list(data.get("topic_tags") or []),
            company_tags=list(data.get("company_tags") or []),
            source_cluster_ids=list(data.get("source_cluster_ids") or []),
            independent_source_count=int(data.get("independent_source_count") or 0),
            status=KnowledgeStatus(data.get("status") or KnowledgeStatus.ACTIVE.value),
            invalidated_at=data.get("invalidated_at"),
            invalidation_reason=str(data.get("invalidation_reason") or ""),
            lineage=dict(data.get("lineage") or {}),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


class KnowledgeStore:
    """Durable knowledge store keyed by claim_id / knowledge_id."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_KNOWLEDGE_PATH
        self._by_id: dict[str, KnowledgeRecord] = {}
        self._by_claim: dict[str, str] = {}

    def get(self, knowledge_id: str) -> KnowledgeRecord | None:
        return self._by_id.get(knowledge_id)

    def get_by_claim(self, claim_id: str) -> KnowledgeRecord | None:
        kid = self._by_claim.get(claim_id)
        return self._by_id.get(kid) if kid else None

    def all(self) -> list[KnowledgeRecord]:
        return list(self._by_id.values())

    def list_active(self) -> list[KnowledgeRecord]:
        return [r for r in self.all() if r.status is KnowledgeStatus.ACTIVE]

    def upsert(self, record: KnowledgeRecord) -> KnowledgeRecord:
        existing = self.get_by_claim(record.claim_id) or self.get(record.knowledge_id)
        now = now_iso()
        if existing is not None:
            record.knowledge_id = existing.knowledge_id
            record.created_at = existing.created_at or now
            if existing.status is KnowledgeStatus.INVALIDATED and record.status is KnowledgeStatus.ACTIVE:
                # Keep invalidation unless explicitly re-activated by sync rules.
                pass
        else:
            record.created_at = record.created_at or now
        record.updated_at = now
        self._by_id[record.knowledge_id] = record
        self._by_claim[record.claim_id] = record.knowledge_id
        return record

    def invalidate(self, claim_id: str, *, reason: str) -> KnowledgeRecord | None:
        record = self.get_by_claim(claim_id)
        if record is None:
            return None
        record.status = KnowledgeStatus.INVALIDATED
        record.invalidated_at = now_iso()
        record.invalidation_reason = reason
        record.updated_at = record.invalidated_at
        self._by_id[record.knowledge_id] = record
        return record

    def load(self, path: str | Path | None = None) -> int:
        target = Path(path) if path else self.path
        self.path = target
        if not target.exists():
            return 0
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        rows = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return 0
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            record = KnowledgeRecord.from_dict(row)
            if not record.knowledge_id or not record.claim_id:
                continue
            self._by_id[record.knowledge_id] = record
            self._by_claim[record.claim_id] = record.knowledge_id
            count += 1
        return count

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": now_iso(),
            "records": [r.to_dict() for r in self.all()],
        }
        fd, tmp_name = tempfile.mkstemp(prefix="knowledge_", suffix=".json", dir=str(target.parent))
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
    def load_or_create(cls, path: str | Path | None = None) -> KnowledgeStore:
        store = cls(path=path)
        store.load()
        return store


def _independent_source_count(cluster_ids: list[str], url_count: int) -> int:
    clusters = [c for c in cluster_ids if c]
    if clusters:
        return len(set(clusters))
    return max(url_count, 0)


def sync_knowledge_from_atoms(
    *,
    atom_store: ResearchAtomStore | None = None,
    atoms_path: str | Path | None = None,
    knowledge_store: KnowledgeStore | None = None,
    knowledge_path: str | Path | None = None,
    persist: bool = True,
) -> list[KnowledgeRecord]:
    """Import only ClaimStatus.VERIFIED; invalidate knowledge when claim rejected."""
    atoms = atom_store or ResearchAtomStore.load_or_create(atoms_path or DEFAULT_ATOMS_PATH)
    store = knowledge_store or KnowledgeStore.load_or_create(knowledge_path or DEFAULT_KNOWLEDGE_PATH)
    synced: list[KnowledgeRecord] = []

    for claim in atoms.claims.values():
        if claim.status is ClaimStatus.REJECTED:
            invalidated = store.invalidate(claim.id, reason="claim_rejected")
            if invalidated is not None:
                synced.append(invalidated)
            continue
        if claim.status is not ClaimStatus.VERIFIED:
            continue

        sources = [atoms.sources[sid] for sid in claim.source_ids if sid in atoms.sources]
        lineage = atoms.lineage.get(claim.id) or {}
        cluster_ids = list(lineage.get("source_cluster_ids") or [])
        if not cluster_ids and lineage.get("source_cluster_id"):
            cluster_ids = [str(lineage.get("source_cluster_id"))]
        urls = [s.url for s in sources if s.url]
        kid = make_knowledge_id(claim.id)
        existing = store.get_by_claim(claim.id)
        record = KnowledgeRecord(
            knowledge_id=existing.knowledge_id if existing else kid,
            claim_id=claim.id,
            claim_text=claim.text,
            claim_type=claim.type.value,
            verified_at=claim.reviewed_at,
            reviewer=str(lineage.get("reviewer") or claim.review_note or ""),
            evidence_ids=list(claim.evidence_ids),
            source_document_ids=list(claim.source_ids),
            canonical_urls=urls,
            publishers=[s.source_name for s in sources if s.source_name],
            published_at=[s.published_at for s in sources],
            source_types=[s.source_type for s in sources],
            source_tiers=[str(lineage.get("source_tier") or "")] if lineage.get("source_tier") else [],
            topic_tags=list(lineage.get("topic_tags") or []),
            company_tags=list(lineage.get("company_tags") or []),
            source_cluster_ids=cluster_ids,
            independent_source_count=_independent_source_count(cluster_ids, len(urls)),
            status=KnowledgeStatus.ACTIVE,
            lineage={
                "intake": lineage.get("intake")
                or ("discovery" if any(s.discovery_provider for s in sources) else "registry"),
                "discovery_provider": lineage.get("discovery_provider")
                or (sources[0].discovery_provider if sources else ""),
                "discovery_query": lineage.get("discovery_query")
                or (sources[0].discovery_query if sources else ""),
                "candidate_id": lineage.get("candidate_id")
                or (sources[0].discovery_candidate_id if sources else ""),
                "claim_id": claim.id,
            },
        )
        # Prefer reviewer from audit note pattern if present
        if claim.review_note and not record.reviewer:
            record.reviewer = claim.review_note
        store.upsert(record)
        synced.append(record)

    if persist:
        store.save()
    return synced
