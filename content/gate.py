"""Content Hard Gate — extends publishing.editorial_gate for claim-level lineage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from content.candidates import freshness_window_hours
from content.models import (
    ContentCandidate,
    ContentCandidateStatus,
    ContentType,
    StatementKind,
)
from publishing.editorial_gate import (
    EditorialGateErrorCode,
    EditorialGateResult,
    GateIssue,
    run_daily_editorial_gate,
)
from research.atom_store import ResearchAtomStore
from research.models import ClaimStatus

# Additional codes for content pipeline (extend, don't duplicate).
if not hasattr(EditorialGateErrorCode, "UNSUPPORTED_CAUSAL_INFERENCE"):
    EditorialGateErrorCode.UNSUPPORTED_CAUSAL_INFERENCE = "UNSUPPORTED_CAUSAL_INFERENCE"
if not hasattr(EditorialGateErrorCode, "STALE_PRIMARY_SIGNAL"):
    EditorialGateErrorCode.STALE_PRIMARY_SIGNAL = "STALE_PRIMARY_SIGNAL"
if not hasattr(EditorialGateErrorCode, "CONTENT_TYPE_MISMATCH"):
    EditorialGateErrorCode.CONTENT_TYPE_MISMATCH = "CONTENT_TYPE_MISMATCH"
if not hasattr(EditorialGateErrorCode, "CLAIM_NOT_VERIFIED"):
    EditorialGateErrorCode.CLAIM_NOT_VERIFIED = "CLAIM_NOT_VERIFIED"
if not hasattr(EditorialGateErrorCode, "ORPHAN_FACT"):
    EditorialGateErrorCode.ORPHAN_FACT = "ORPHAN_FACT"
if not hasattr(EditorialGateErrorCode, "UNSUPPORTED_ENTITY"):
    EditorialGateErrorCode.UNSUPPORTED_ENTITY = "UNSUPPORTED_ENTITY"

NON_BYPASSABLE = frozenset(
    {
        EditorialGateErrorCode.UNSUPPORTED_FACT,
        EditorialGateErrorCode.SOURCE_LINEAGE_INCOMPLETE,
        EditorialGateErrorCode.FABRICATED_DATA,
        EditorialGateErrorCode.FUTURE_PUBLICATION,
        EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE,
        EditorialGateErrorCode.CLAIM_NOT_VERIFIED,
        EditorialGateErrorCode.ORPHAN_FACT,
        EditorialGateErrorCode.UNSUPPORTED_ENTITY,
    }
)

_NUMERIC_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|亿元|万元|元/柜|元|SKU|台|天|小时|百分点|倍|分|星)|"
    r"(第\s*\d+\s*天)|(\d+\s*%)|预测\s*\d+|Prediction\s*\d+",
    re.I,
)

_CAUSAL_MARKERS = (
    "带动",
    "导致",
    "证明",
    "说明渠道",
    "渠道动销",
    "因此智能柜",
    "所以智能柜",
)


@dataclass
class CoverageReport:
    total_factual_claims: int = 0
    verified_factual_claims: int = 0
    unsupported_factual_claims: int = 0
    numeric_claims: int = 0
    supported_numeric_claims: int = 0
    unsupported_numeric_claims: int = 0
    source_count: int = 0
    independent_source_count: int = 0
    inferences: int = 0
    hypotheses: int = 0
    experiment_parameters: int = 0
    gate_errors: list[str] = field(default_factory=list)
    gate_warnings: list[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict:
        return {
            "total_factual_claims": self.total_factual_claims,
            "verified_factual_claims": self.verified_factual_claims,
            "unsupported_factual_claims": self.unsupported_factual_claims,
            "numeric_claims": self.numeric_claims,
            "supported_numeric_claims": self.supported_numeric_claims,
            "unsupported_numeric_claims": self.unsupported_numeric_claims,
            "source_count": self.source_count,
            "independent_source_count": self.independent_source_count,
            "inferences": self.inferences,
            "hypotheses": self.hypotheses,
            "experiment_parameters": self.experiment_parameters,
            "gate_errors": list(self.gate_errors),
            "gate_warnings": list(self.gate_warnings),
            "passed": self.passed,
            "result": "PASS" if self.passed else "FAIL",
        }


def _issue(code: str, message: str, location: str = "") -> GateIssue:
    return GateIssue(code=code, message=message, location=location)


def run_content_hard_gate(
    candidate: ContentCandidate,
    *,
    atom_store: ResearchAtomStore | None = None,
    now_date: str | None = None,
) -> EditorialGateResult:
    """Run content-level hard gate. Mutates candidate.status / gate_result."""
    errors: list[GateIssue] = []
    warnings: list[GateIssue] = []
    coverage = CoverageReport(
        source_count=len(candidate.source_document_ids),
        independent_source_count=candidate.independent_source_count,
    )

    # Reuse daily structural gate on draft payload when present.
    payload = dict(candidate.draft or {})
    payload.setdefault("title", candidate.primary_signal)
    payload.setdefault("primary_signal_count", candidate.primary_signal_count)
    payload.setdefault("content_type", candidate.content_type.value)
    if candidate.content_type is ContentType.DAILY:
        now_arg: date | None = None
        if now_date:
            now_arg = datetime.strptime(str(now_date)[:10], "%Y-%m-%d").date()
        base = run_daily_editorial_gate(payload, now=now_arg)
        errors.extend(base.errors)
        warnings.extend(base.warnings)

    if candidate.content_type is ContentType.DAILY and candidate.primary_signal_count != 1:
        errors.append(
            _issue(
                EditorialGateErrorCode.MULTI_SIGNAL_DAILY,
                f"primary_signal_count={candidate.primary_signal_count} must be 1 for Daily",
                "primary_signal_count",
            )
        )

    if candidate.content_type is ContentType.INSIGHT and not candidate.theme_consistency:
        errors.append(
            _issue(
                EditorialGateErrorCode.CONTENT_TYPE_MISMATCH,
                "Insight candidate lacks theme_consistency across claims",
                "theme_consistency",
            )
        )

    # Freshness for Daily primary signal
    window = freshness_window_hours(candidate.content_type)
    if (
        candidate.content_type is ContentType.DAILY
        and window is not None
        and candidate.freshness_hours is not None
        and candidate.freshness_hours > window
    ):
        errors.append(
            _issue(
                EditorialGateErrorCode.STALE_PRIMARY_SIGNAL,
                f"primary signal age {candidate.freshness_hours:.1f}h exceeds window {window}h",
                "freshness_hours",
            )
        )

    # Claim-level lineage
    for stmt in candidate.statements:
        if stmt.kind is StatementKind.FACT:
            coverage.total_factual_claims += 1
            if not stmt.claim_ids:
                coverage.unsupported_factual_claims += 1
                errors.append(
                    _issue(
                        EditorialGateErrorCode.UNSUPPORTED_FACT,
                        "FACT statement missing claim_id",
                        "statements",
                    )
                )
                continue
            verified = True
            if atom_store is not None:
                for cid in stmt.claim_ids:
                    claim = atom_store.get_claim(cid)
                    if claim is None or claim.status is not ClaimStatus.VERIFIED:
                        verified = False
                        errors.append(
                            _issue(
                                EditorialGateErrorCode.CLAIM_NOT_VERIFIED,
                                f"FACT claim {cid} is not ClaimStatus.VERIFIED",
                                cid,
                            )
                        )
            if verified:
                coverage.verified_factual_claims += 1
            else:
                coverage.unsupported_factual_claims += 1

            # Causal overreach: company finance → channel conclusion without claim support
            text = stmt.text
            if any(m in text for m in _CAUSAL_MARKERS) and "智能柜渠道" in text:
                if not any("渠道" in (atom_store.get_claim(cid).text if atom_store and atom_store.get_claim(cid) else "") for cid in stmt.claim_ids):
                    # If statement itself asserts channel from company totals
                    if "营收" in text or "净利润" in text or candidate.metadata.get("causal_overreach"):
                        errors.append(
                            _issue(
                                EditorialGateErrorCode.UNSUPPORTED_CAUSAL_INFERENCE,
                                "Company-level finance used to assert channel/动销 conclusion",
                                "statements",
                            )
                        )

            if _NUMERIC_RE.search(stmt.text):
                coverage.numeric_claims += 1
                if stmt.numeric_kind in {"SOURCE_FACT", "DERIVED_METRIC", "EXPERIMENT_PARAMETER"}:
                    if stmt.numeric_kind == "DERIVED_METRIC" and (
                        not stmt.formula or not stmt.inputs or not stmt.claim_ids
                    ):
                        coverage.unsupported_numeric_claims += 1
                        errors.append(
                            _issue(
                                EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM,
                                "DERIVED_METRIC requires formula, inputs, and claim_ids",
                                "statements",
                            )
                        )
                    elif stmt.numeric_kind == "EXPERIMENT_PARAMETER" and not stmt.labeled_experiment:
                        coverage.unsupported_numeric_claims += 1
                        errors.append(
                            _issue(
                                EditorialGateErrorCode.UNLABELED_EXPERIMENT_PARAMETER,
                                "Experiment parameter missing ZeroRealm label",
                                "statements",
                            )
                        )
                    else:
                        coverage.supported_numeric_claims += 1
                else:
                    coverage.unsupported_numeric_claims += 1
                    errors.append(
                        _issue(
                            EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM,
                            "Numeric statement lacks SOURCE_FACT/DERIVED_METRIC/EXPERIMENT_PARAMETER",
                            "statements",
                        )
                    )

        elif stmt.kind is StatementKind.INFERENCE:
            coverage.inferences += 1
            if not stmt.claim_ids:
                errors.append(
                    _issue(
                        EditorialGateErrorCode.UNSUPPORTED_FACT,
                        "INFERENCE must cite supporting claim_ids",
                        "statements",
                    )
                )
        elif stmt.kind is StatementKind.HYPOTHESIS:
            coverage.hypotheses += 1
        elif stmt.kind is StatementKind.EXPERIMENT_PARAMETER:
            coverage.experiment_parameters += 1
            if not stmt.labeled_experiment:
                errors.append(
                    _issue(
                        EditorialGateErrorCode.UNLABELED_EXPERIMENT_PARAMETER,
                        "EXPERIMENT_PARAMETER must be labeled",
                        "statements",
                    )
                )

    # Snippet evidence
    if candidate.metadata.get("evidence_source_type") in {
        "search_snippet",
        "provider_content",
        "anysearch_snippet",
    }:
        errors.append(
            _issue(
                EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE,
                "Search snippet cannot back factual content",
                "metadata.evidence_source_type",
            )
        )

    # Future publication on package/draft dates
    published_at = (candidate.draft or {}).get("published_at") or candidate.metadata.get("published_at")
    if published_at and now_date and str(published_at)[:10] > str(now_date)[:10]:
        errors.append(
            _issue(
                EditorialGateErrorCode.FUTURE_PUBLICATION,
                f"published_at {published_at} is in the future vs {now_date}",
                "published_at",
            )
        )

    # Lineage completeness
    if coverage.total_factual_claims and not candidate.source_document_ids:
        errors.append(
            _issue(
                EditorialGateErrorCode.SOURCE_LINEAGE_INCOMPLETE,
                "Factual claims present without source_document_ids",
                "source_document_ids",
            )
        )

    # Deduplicate error codes for coverage
    coverage.gate_errors = sorted({e.code for e in errors})
    coverage.gate_warnings = sorted({w.code for w in warnings})
    coverage.passed = not errors

    result = EditorialGateResult(
        status="passed" if coverage.passed else "failed",
        errors=errors,
        warnings=warnings,
    )
    candidate.gate_result = {
        **result.to_dict(),
        "passed": result.passed,
        "coverage": coverage.to_dict(),
        "gate_version": "content-hard-gate-v1",
        "non_bypassable_hit": sorted(
            {e.code for e in errors if e.code in NON_BYPASSABLE}
        ),
    }
    candidate.status = (
        ContentCandidateStatus.READY_FOR_EDITORIAL
        if coverage.passed
        else ContentCandidateStatus.GATE_FAILED
    )
    return result
