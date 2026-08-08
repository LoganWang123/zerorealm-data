"""Helpers to convert raw news items into research atoms."""

from __future__ import annotations

from dataclasses import dataclass

from research.models import (
    Claim,
    ClaimStatus,
    ClaimType,
    Confidence,
    Evidence,
    SourceDocument,
    make_claim_id,
    make_evidence_id,
    make_source_id,
)


@dataclass
class ResearchAtoms:
    source: SourceDocument
    evidence: list[Evidence]
    claims: list[Claim]


def news_to_research_atoms(item: dict) -> ResearchAtoms:
    """Convert one public news item into source / evidence / claim atoms.

    Mapping:
    - excerpt/title → FACT (draft)
    - insight → INFERENCE based on the fact
    - opinion → OPINION
    """
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    source_name = str(item.get("source_name") or "").strip() or "unknown"
    published_at = item.get("published_at")
    excerpt = str(item.get("excerpt") or "").strip()
    insight = str(item.get("insight") or "").strip()
    opinion = str(item.get("opinion") or "").strip()

    source = SourceDocument(
        id=make_source_id(url, title),
        url=url,
        title=title,
        source_name=source_name,
        published_at=str(published_at) if published_at else None,
        raw_excerpt=excerpt,
        discovery_provider=str(item.get("discovery_provider") or "").strip(),
        discovery_query=str(item.get("discovery_query") or "").strip(),
        discovery_candidate_id=str(item.get("discovery_candidate_id") or "").strip(),
        discovery_original_url=str(item.get("discovery_original_url") or url).strip(),
    )

    fact_text = excerpt or title
    evidence = [
        Evidence(
            id=make_evidence_id(source.id, fact_text),
            source_id=source.id,
            quote=fact_text,
        )
    ]

    fact = Claim(
        id=make_claim_id(fact_text, ClaimType.FACT),
        text=fact_text,
        type=ClaimType.FACT,
        status=ClaimStatus.DRAFT,
        confidence=Confidence.MEDIUM,
        source_ids=[source.id],
        evidence_ids=[evidence[0].id],
    )
    claims = [fact]

    if insight:
        claims.append(
            Claim(
                id=make_claim_id(insight, ClaimType.INFERENCE),
                text=insight,
                type=ClaimType.INFERENCE,
                status=ClaimStatus.DRAFT,
                confidence=Confidence.MEDIUM,
                source_ids=[source.id],
                based_on_claim_ids=[fact.id],
            )
        )

    if opinion:
        claims.append(
            Claim(
                id=make_claim_id(opinion, ClaimType.OPINION),
                text=opinion,
                type=ClaimType.OPINION,
                status=ClaimStatus.DRAFT,
                confidence=Confidence.LOW,
                source_ids=[source.id],
            )
        )

    return ResearchAtoms(source=source, evidence=evidence, claims=claims)
