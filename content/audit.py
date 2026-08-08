"""Post-generation Claim Audit — independent deterministic protection after LLM output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from content.allowed_facts import AllowedFactsContext, build_allowed_facts
from content.gate import run_content_hard_gate
from content.generator import DraftStatement, StructuredDraft
from content.models import (
    ContentCandidate,
    ContentCandidateStatus,
    ContentStatement,
    StatementKind,
)
from publishing.editorial_gate import EditorialGateErrorCode, EditorialGateResult, GateIssue
from research.atom_store import ResearchAtomStore
from research.models import ClaimStatus

# Ensure codes exist on EditorialGateErrorCode
for _code in ("ORPHAN_FACT", "UNSUPPORTED_ENTITY", "CHANNEL_REVIEW_REQUIRED"):
    if not hasattr(EditorialGateErrorCode, _code):
        setattr(EditorialGateErrorCode, _code, _code)

_NUMERIC_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|亿元|万元|元/柜|元|SKU|台|天|小时|百分点|倍|分|星)|"
    r"(第\s*\d+\s*天)|(\d+\s*%)|预测\s*\d+|Prediction\s*\d+|★+",
    re.I,
)

_CAUSAL_MARKERS = (
    "带动",
    "导致",
    "证明",
    "说明其智能柜渠道",
    "说明其智能柜",
    "渠道动销能力",
    "因此智能柜",
    "所以智能柜",
)

# Known brand/company tokens used for unsupported-entity detection (not grammar words).
_ENTITY_CANDIDATES = (
    "星巴克",
    "瑞幸",
    "麦当劳",
    "肯德基",
    "阿里巴巴",
    "腾讯",
    "京东",
    "美团",
    "拼多多",
    "华为",
    "小米",
    "字节跳动",
    "沃尔玛",
    "永辉",
    "友宝",
    "东鹏饮料",
    "东鹏",
    "云拿",
    "映翰通",
    "雷允上",
)


@dataclass
class AuditReport:
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    orphan_facts: int = 0
    unsupported_entities: list[str] = field(default_factory=list)
    unsupported_numbers: list[str] = field(default_factory=list)
    gate_result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "result": "PASS" if self.passed else "FAIL",
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "orphan_facts": self.orphan_facts,
            "unsupported_entities": list(self.unsupported_entities),
            "unsupported_numbers": list(self.unsupported_numbers),
            "gate_result": dict(self.gate_result),
        }


def _issue(code: str, message: str, location: str = "") -> GateIssue:
    return GateIssue(code=code, message=message, location=location)


def extract_statements_from_draft(draft: StructuredDraft | dict) -> list[DraftStatement]:
    if isinstance(draft, StructuredDraft):
        return list(draft.statements)
    return [DraftStatement.from_dict(s) for s in (draft.get("statements") or [])]


def sync_candidate_statements_from_draft(
    candidate: ContentCandidate,
    draft: StructuredDraft | dict,
) -> None:
    """Re-map draft statements onto candidate for Hard Gate reuse."""
    mapped: list[ContentStatement] = []
    for stmt in extract_statements_from_draft(draft):
        kind = StatementKind(stmt.statement_type)
        claim_ids = list(stmt.claim_ids)
        if kind is StatementKind.INFERENCE and stmt.supporting_claim_ids:
            claim_ids = list(stmt.supporting_claim_ids)
        mapped.append(
            ContentStatement(
                kind=kind,
                text=stmt.text,
                claim_ids=claim_ids,
                numeric_kind=stmt.numeric_kind,
                formula=stmt.formula,
                inputs=list(stmt.inputs),
                labeled_experiment=bool(stmt.zerorealm_suggested),
            )
        )
    candidate.statements = mapped


def _normalize_number(token: str) -> str:
    return re.sub(r"\s+", "", token or "").lower()


def _allowed_number_set(context: AllowedFactsContext) -> set[str]:
    return {_normalize_number(n) for n in context.allowed_numbers}


def audit_structured_draft(
    candidate: ContentCandidate,
    draft: StructuredDraft | dict,
    *,
    atom_store: ResearchAtomStore | None = None,
    allowed: AllowedFactsContext | None = None,
    now_date: str | None = None,
) -> AuditReport:
    """Re-extract statements, scan entities/numbers, then run Hard Gate."""
    context = allowed or build_allowed_facts(candidate, atom_store=atom_store)
    statements = extract_statements_from_draft(draft)
    errors: list[GateIssue] = []
    report = AuditReport()

    allowed_claim_ids = {c.claim_id for c in context.allowed_claims}
    allowed_entities = set(context.allowed_entities)
    allowed_nums = _allowed_number_set(context)

    for stmt in statements:
        if stmt.statement_type == "FACT":
            # Orphan fact: missing / non-verified claim
            if not stmt.claim_ids:
                report.orphan_facts += 1
                errors.append(
                    _issue(
                        EditorialGateErrorCode.ORPHAN_FACT,
                        "FACT statement missing claim_id",
                        "statements",
                    )
                )
            else:
                for cid in stmt.claim_ids:
                    verified = cid in allowed_claim_ids
                    if atom_store is not None:
                        claim = atom_store.get_claim(cid)
                        verified = (
                            claim is not None and claim.status is ClaimStatus.VERIFIED
                        )
                    if not verified:
                        report.orphan_facts += 1
                        errors.append(
                            _issue(
                                EditorialGateErrorCode.ORPHAN_FACT,
                                f"FACT cites non-VERIFIED claim {cid}",
                                cid,
                            )
                        )

            # Unsupported entity as fact
            for entity in _ENTITY_CANDIDATES:
                if entity in stmt.text and entity not in allowed_entities:
                    report.unsupported_entities.append(entity)
                    errors.append(
                        _issue(
                            EditorialGateErrorCode.UNSUPPORTED_ENTITY,
                            f"Unsupported entity used as fact: {entity}",
                            "statements",
                        )
                    )

            # Unsupported number
            for match in _NUMERIC_RE.finditer(stmt.text):
                token = match.group(0)
                # Skip star-only pseudo markers handled below
                if "★" in token:
                    continue
                norm = _normalize_number(token)
                # Digits alone that appear in allowed claim text are ok via allowed_numbers
                if norm and norm not in allowed_nums:
                    # Experiment params may introduce their own labeled numbers
                    if stmt.numeric_kind == "EXPERIMENT_PARAMETER" and stmt.zerorealm_suggested:
                        continue
                    if stmt.numeric_kind == "DERIVED_METRIC" and stmt.formula and stmt.inputs:
                        continue
                    report.unsupported_numbers.append(token)
                    errors.append(
                        _issue(
                            EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM,
                            f"Unsupported number in draft: {token}",
                            "statements",
                        )
                    )

            # Causal overreach
            text = stmt.text
            if any(m in text for m in _CAUSAL_MARKERS):
                supporting = " ".join(
                    (atom_store.get_claim(cid).text if atom_store and atom_store.get_claim(cid) else "")
                    for cid in stmt.claim_ids
                )
                if "渠道" not in supporting and "动销" not in supporting:
                    errors.append(
                        _issue(
                            EditorialGateErrorCode.UNSUPPORTED_CAUSAL_INFERENCE,
                            "Company-level fact used to assert channel/动销 conclusion",
                            "statements",
                        )
                    )

            # Pseudo precision without methodology
            if re.search(r"Prediction\s*\d+|预测\s*\d+%|★{2,}|第\s*\d+\s*天", text, re.I):
                if not candidate.metadata.get("methodology_disclosed"):
                    errors.append(
                        _issue(
                            EditorialGateErrorCode.PSEUDO_PRECISION,
                            "Pseudo-precise prediction/trend without methodology",
                            "statements",
                        )
                    )

            # Industry standard without verified source
            if "行业标准" in text or "行业平均" in text:
                errors.append(
                    _issue(
                        EditorialGateErrorCode.UNSUPPORTED_FACT,
                        "Industry standard/average asserted without verified source in Allowed Facts",
                        "statements",
                    )
                )

        elif stmt.statement_type == "EXPERIMENT_PARAMETER":
            if stmt.industry_standard and not stmt.zerorealm_suggested:
                errors.append(
                    _issue(
                        EditorialGateErrorCode.UNLABELED_EXPERIMENT_PARAMETER,
                        "Experiment parameter claimed as industry_standard without source",
                        "statements",
                    )
                )
            if not stmt.zerorealm_suggested:
                errors.append(
                    _issue(
                        EditorialGateErrorCode.UNLABELED_EXPERIMENT_PARAMETER,
                        "EXPERIMENT_PARAMETER must set zerorealm_suggested=true",
                        "statements",
                    )
                )

    # Sync to candidate + Hard Gate
    sync_candidate_statements_from_draft(candidate, draft)
    if isinstance(draft, StructuredDraft):
        if not candidate.draft:
            from content.generator import _structured_to_candidate_draft

            candidate.draft = _structured_to_candidate_draft(draft, candidate)
        else:
            candidate.draft["statements"] = [s.to_dict() for s in statements]
            candidate.metadata["structured_draft"] = draft.to_dict()

    gate = run_content_hard_gate(candidate, atom_store=atom_store, now_date=now_date)

    # Merge audit-specific errors into gate_result
    merged_errors = list(gate.errors) + errors
    # Deduplicate by code+message
    seen: set[tuple[str, str]] = set()
    unique: list[GateIssue] = []
    for err in merged_errors:
        key = (err.code, err.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(err)

    passed = not unique
    result = EditorialGateResult(
        status="passed" if passed else "failed",
        errors=unique,
        warnings=list(gate.warnings),
    )
    candidate.gate_result = {
        **result.to_dict(),
        "passed": result.passed,
        "coverage": (candidate.gate_result or {}).get("coverage") or {},
        "gate_version": "content-hard-gate-v1+post-gen-audit",
        "non_bypassable_hit": sorted(
            {
                e.code
                for e in unique
                if e.code
                in {
                    EditorialGateErrorCode.UNSUPPORTED_FACT,
                    EditorialGateErrorCode.SOURCE_LINEAGE_INCOMPLETE,
                    EditorialGateErrorCode.FABRICATED_DATA,
                    EditorialGateErrorCode.FUTURE_PUBLICATION,
                    EditorialGateErrorCode.SEARCH_SNIPPET_AS_EVIDENCE,
                    EditorialGateErrorCode.CLAIM_NOT_VERIFIED,
                    EditorialGateErrorCode.ORPHAN_FACT,
                    EditorialGateErrorCode.UNSUPPORTED_ENTITY,
                    EditorialGateErrorCode.UNSUPPORTED_NUMERIC_CLAIM,
                    EditorialGateErrorCode.UNSUPPORTED_CAUSAL_INFERENCE,
                }
            }
        ),
        "audit": {
            "orphan_facts": report.orphan_facts,
            "unsupported_entities": sorted(set(report.unsupported_entities)),
            "unsupported_numbers": list(report.unsupported_numbers),
        },
    }
    candidate.status = (
        ContentCandidateStatus.READY_FOR_EDITORIAL
        if passed
        else ContentCandidateStatus.GATE_FAILED
    )
    report.passed = passed
    report.errors = sorted({e.code for e in unique})
    report.warnings = sorted({w.code for w in gate.warnings})
    report.gate_result = dict(candidate.gate_result)
    report.unsupported_entities = sorted(set(report.unsupported_entities))
    return report
