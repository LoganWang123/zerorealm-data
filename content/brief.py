"""Editorial Brief + internal Draft builders (staging only, no publish)."""

from __future__ import annotations

import json
from pathlib import Path

from content.models import ContentCandidate, ContentType, StatementKind
from content.store import load_content_config
from utils.helpers import now_iso


def build_editorial_brief(candidate: ContentCandidate) -> dict:
    facts = [s for s in candidate.statements if s.kind is StatementKind.FACT]
    inferences = [s for s in candidate.statements if s.kind is StatementKind.INFERENCE]
    hypotheses = [s for s in candidate.statements if s.kind is StatementKind.HYPOTHESIS]
    experiments = [
        s for s in candidate.statements if s.kind is StatementKind.EXPERIMENT_PARAMETER
    ]
    brief = {
        "title": candidate.primary_signal[:80] or candidate.topic,
        "working_title": candidate.primary_signal[:80] or candidate.topic,
        "content_type": candidate.content_type.value,
        "primary_signal": candidate.primary_signal,
        "why_it_matters": candidate.research_question,
        "allowed_facts": [
            {"claim_id": cid, "text": s.text}
            for s in facts
            for cid in (s.claim_ids or [""])
        ],
        "verified_claim_ids": list(candidate.claim_ids),
        "source_map": {
            "source_document_ids": list(candidate.source_document_ids),
            "evidence_ids": list(candidate.evidence_ids),
            "independent_source_count": candidate.independent_source_count,
        },
        "fact_inference_boundary": {
            "facts": [s.to_dict() for s in facts],
            "inferences": [s.to_dict() for s in inferences],
            "hypotheses": [s.to_dict() for s in hypotheses],
            "experiment_parameters": [s.to_dict() for s in experiments],
        },
        "known_evidence_gaps": list(candidate.evidence_gaps),
        "suggested_operating_question": candidate.research_question,
        "suggested_metric_check": "核对主信号对应运营指标是否可观察、可回撤",
        "suggested_reversible_action": "小范围试点并设定回撤条件",
        "prohibited_unsupported_claims": list(candidate.evidence_gaps),
        "hard_gate_preview": {
            "primary_signal_count": candidate.primary_signal_count,
            "content_type": candidate.content_type.value,
            "freshness_hours": candidate.freshness_hours,
        },
        "generated_at": now_iso(),
    }
    candidate.brief = brief
    return brief


def build_internal_draft(candidate: ContentCandidate) -> dict:
    """Create internal review draft artifact — never production content paths."""
    if not candidate.brief:
        build_editorial_brief(candidate)
    statements = []
    for stmt in candidate.statements:
        block = {
            "kind": stmt.kind.value,
            "text": stmt.text,
            "claim_ids": list(stmt.claim_ids),
        }
        if stmt.kind is StatementKind.EXPERIMENT_PARAMETER:
            block["label"] = "ZeroRealm suggested experiment parameter"
            block["labeled_experiment"] = True
        if stmt.numeric_kind:
            block["numeric_kind"] = stmt.numeric_kind
            block["formula"] = stmt.formula
            block["inputs"] = list(stmt.inputs)
        statements.append(block)

    primary_url = ""
    # Prefer first source document URL from metadata if provided by caller.
    urls = list(candidate.metadata.get("canonical_urls") or [])
    if not urls and candidate.source_document_ids:
        primary_url = f"source:{candidate.source_document_ids[0]}"
    elif urls:
        primary_url = urls[0]

    def _section(title: str, excerpt: str, claim_ids: list[str]) -> dict:
        return {
            "level": "core",
            "title": title,
            "excerpt": excerpt,
            "claim_ids": list(claim_ids),
            "source_url": primary_url or "https://fixture.local/source",
            "source_name": "verified-source",
            "source_type": "web",
        }

    draft = {
        "content_id": candidate.content_id,
        "content_type": candidate.content_type.value,
        "slug": candidate.slug,
        "title": candidate.brief.get("title") or candidate.primary_signal,
        "summary": candidate.research_question,
        "body": "\n\n".join(
            f"[{s['kind']}] {s['text']}"
            + (f" (claims: {', '.join(s['claim_ids'])})" if s.get("claim_ids") else "")
            for s in statements
        ),
        "statements": statements,
        "primary_signal": candidate.primary_signal,
        "primary_signal_count": candidate.primary_signal_count,
        "source_url": primary_url or "https://fixture.local/source",
        "sections": [
            _section(candidate.primary_signal, candidate.primary_signal, list(candidate.claim_ids[:1]))
        ]
        if candidate.content_type is ContentType.DAILY
        else [
            _section(s.text[:60], s.text, list(s.claim_ids))
            for s in candidate.statements
            if s.kind is StatementKind.FACT
        ],
        "claim_map": {cid: True for cid in candidate.claim_ids},
        "source_map": {
            "source_document_ids": list(candidate.source_document_ids),
            "evidence_ids": list(candidate.evidence_ids),
            "independent_source_count": candidate.independent_source_count,
        },
        "generated_at": now_iso(),
        "staging_only": True,
        "wechat_published": False,
        "website_published": False,
    }
    # Multi-signal daily fixtures may set primary_signal_count > 1 and multiple cores
    if candidate.primary_signal_count > 1 and candidate.content_type is ContentType.DAILY:
        draft["sections"] = [
            _section(signal, signal, list(candidate.claim_ids[:1]))
            for signal in ([candidate.primary_signal] + list(candidate.metadata.get("extra_signals") or []))[
                : candidate.primary_signal_count
            ]
        ]
        draft["primary_signal_count"] = candidate.primary_signal_count

    candidate.draft = draft
    return draft


def write_review_draft(candidate: ContentCandidate, *, base_dir: str | Path | None = None) -> Path:
    cfg = load_content_config()
    root = Path(base_dir or (cfg.get("paths") or {}).get("review_drafts") or "dist/review/content")
    root.mkdir(parents=True, exist_ok=True)
    if not candidate.draft:
        build_internal_draft(candidate)
    path = root / f"{candidate.content_type.value}__{candidate.slug}__{candidate.content_id}.json"
    path.write_text(json.dumps(candidate.draft, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate.metadata["review_draft_path"] = str(path)
    return path
