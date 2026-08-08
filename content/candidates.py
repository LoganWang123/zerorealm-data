"""Build Content Candidates from active Knowledge only."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from content.models import (
    ContentCandidate,
    ContentCandidateStatus,
    ContentStatement,
    ContentType,
    StatementKind,
    make_content_candidate_id,
    make_content_id,
    touch_timestamps,
)
from content.store import ContentCandidateStore, load_content_config, parse_window_to_hours
from discovery.freshness import parse_published_at
from research.knowledge import KnowledgeRecord, KnowledgeStatus, KnowledgeStore
from utils.helpers import now_iso


def _slugify(text: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", (text or "").strip().lower())
    raw = raw.strip("-") or "item"
    return raw[:80]


def _freshness_hours(published_values: list[str | None], *, tz_name: str) -> float | None:
    dates = [parse_published_at(v) for v in published_values]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None
    newest = max(dates)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    now = datetime.now(tz)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=tz)
    delta = now - newest.astimezone(tz)
    return max(0.0, delta.total_seconds() / 3600.0)


def _theme_ok(records: list[KnowledgeRecord], topic: str) -> bool:
    if len(records) <= 1:
        return True
    topic_l = (topic or "").lower()
    hits = 0
    for rec in records:
        blob = f"{rec.claim_text} {' '.join(rec.topic_tags)}".lower()
        if topic_l and topic_l in blob:
            hits += 1
            continue
        if rec.topic_tags and set(rec.topic_tags) & set(records[0].topic_tags):
            hits += 1
            continue
        # shared company tag
        if rec.company_tags and set(rec.company_tags) & set(records[0].company_tags):
            hits += 1
    return hits >= max(1, len(records) - 1)


def build_candidate_from_knowledge(
    records: list[KnowledgeRecord],
    *,
    content_type: ContentType,
    topic: str = "",
    research_question: str = "",
    primary_signals: list[str] | None = None,
    config: dict | None = None,
) -> ContentCandidate:
    """Build one candidate. Only ACTIVE knowledge records are accepted."""
    cfg = config or load_content_config()
    active = [r for r in records if r.status is KnowledgeStatus.ACTIVE]
    if not active:
        raise ValueError("No active VERIFIED knowledge records provided")

    signals = primary_signals or [active[0].claim_text]
    topic_text = topic or (active[0].topic_tags[0] if active[0].topic_tags else active[0].claim_text[:40])
    companies = sorted({tag for r in active for tag in r.company_tags})
    claim_ids = [r.claim_id for r in active]
    knowledge_ids = [r.knowledge_id for r in active]
    evidence_ids = sorted({eid for r in active for eid in r.evidence_ids})
    source_ids = sorted({sid for r in active for sid in r.source_document_ids})
    cluster_ids = sorted({cid for r in active for cid in r.source_cluster_ids if cid})
    independent = len(set(cluster_ids)) if cluster_ids else sum(
        max(1, r.independent_source_count) for r in active
    )
    if cluster_ids:
        independent = len(set(cluster_ids))

    published_vals = [p for r in active for p in r.published_at]
    freshness = _freshness_hours(published_vals, tz_name=str(cfg.get("timezone") or "Asia/Shanghai"))

    statements = [
        ContentStatement(
            kind=StatementKind.FACT,
            text=r.claim_text,
            claim_ids=[r.claim_id],
            numeric_kind="SOURCE_FACT" if any(ch.isdigit() for ch in r.claim_text) else None,
        )
        for r in active
    ]

    gaps: list[str] = []
    if independent < 2 and content_type is ContentType.DAILY:
        gaps.append("independent_source_count < 2 (editorial caution, not auto-fail)")

    key = "|".join(sorted(claim_ids))
    cid = make_content_candidate_id(content_type.value, key)
    slug = _slugify(f"{content_type.value}-{topic_text}")
    candidate = ContentCandidate(
        content_candidate_id=cid,
        content_type=content_type,
        topic=topic_text,
        companies=companies,
        primary_signal=signals[0],
        research_question=research_question or f"围绕「{topic_text}」的运营影响是什么？",
        knowledge_ids=knowledge_ids,
        claim_ids=claim_ids,
        evidence_ids=evidence_ids,
        source_document_ids=source_ids,
        independent_source_count=independent,
        freshness_hours=freshness,
        candidate_reason="Built from active VERIFIED knowledge only",
        evidence_gaps=gaps,
        primary_signal_count=len(signals),
        theme_consistency=_theme_ok(active, topic_text),
        statements=statements,
        status=ContentCandidateStatus.DRAFT,
        slug=slug,
        content_id=make_content_id(content_type.value, slug),
        metadata={
            "source_cluster_ids": cluster_ids,
            "canonical_urls": [u for r in active for u in r.canonical_urls],
            "built_at": now_iso(),
        },
    )
    return touch_timestamps(candidate)


def build_candidates(
    *,
    knowledge_store: KnowledgeStore,
    candidate_store: ContentCandidateStore,
    content_type: ContentType,
    knowledge_ids: list[str] | None = None,
    topic: str = "",
    research_question: str = "",
    primary_signals: list[str] | None = None,
    persist: bool = True,
) -> list[ContentCandidate]:
    cfg = load_content_config()
    if knowledge_ids:
        records = [knowledge_store.get(kid) for kid in knowledge_ids]
        records = [r for r in records if r is not None]
        candidate = build_candidate_from_knowledge(
            records,
            content_type=content_type,
            topic=topic,
            research_question=research_question,
            primary_signals=primary_signals,
            config=cfg,
        )
        candidate_store.upsert(candidate)
        built = [candidate]
    else:
        # Default: one daily candidate per active knowledge item; insight groups by topic tag.
        active = knowledge_store.list_active()
        built = []
        if content_type is ContentType.DAILY:
            for rec in active:
                cand = build_candidate_from_knowledge(
                    [rec],
                    content_type=content_type,
                    topic=topic or (rec.topic_tags[0] if rec.topic_tags else ""),
                    research_question=research_question,
                    config=cfg,
                )
                candidate_store.upsert(cand)
                built.append(cand)
        else:
            groups: dict[str, list] = {}
            for rec in active:
                key = (rec.topic_tags[0] if rec.topic_tags else rec.claim_id)
                groups.setdefault(key, []).append(rec)
            for key, rows in groups.items():
                cand = build_candidate_from_knowledge(
                    rows,
                    content_type=content_type,
                    topic=topic or key,
                    research_question=research_question,
                    config=cfg,
                )
                candidate_store.upsert(cand)
                built.append(cand)
    if persist:
        candidate_store.save()
    return built


def freshness_window_hours(content_type: ContentType, config: dict | None = None) -> float | None:
    cfg = config or load_content_config()
    freshness = cfg.get("freshness") or {}
    if content_type is ContentType.DAILY:
        return parse_window_to_hours(freshness.get("daily_primary_window"))
    return parse_window_to_hours(freshness.get("insight_window"))
