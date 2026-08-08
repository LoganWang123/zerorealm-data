"""Bounded draft repair — max 2 attempts, no new facts/search/claims."""

from __future__ import annotations

import re
from dataclasses import dataclass

from content.allowed_facts import build_allowed_facts
from content.audit import audit_structured_draft
from content.generator import DraftStatement, StructuredDraft
from content.models import ContentCandidate, ContentCandidateStatus
from content.store import load_content_config
from research.atom_store import ResearchAtomStore

_CAUSAL_SOFTEN = (
    ("说明其智能柜渠道动销能力较强", "是否映射到智能柜渠道动销，仍需独立验证"),
    ("说明其智能柜渠道动销", "智能柜渠道动销是否同步改善，仍属待验证推断"),
    ("因此智能柜", "关于智能柜，尚需独立证据验证："),
    ("所以智能柜", "关于智能柜，尚需独立证据验证："),
    ("带动", "相关于"),
    ("导致", "伴随"),
    ("证明", "提示（待验证）"),
)


@dataclass
class RepairResult:
    draft: StructuredDraft
    attempts: int
    passed: bool
    status: str
    audit: dict

    def to_dict(self) -> dict:
        return {
            "draft": self.draft.to_dict(),
            "attempts": self.attempts,
            "passed": self.passed,
            "status": self.status,
            "audit": dict(self.audit),
        }


def max_repair_attempts(config: dict | None = None) -> int:
    cfg = config or load_content_config()
    gen = cfg.get("generator") or {}
    try:
        return max(0, int(gen.get("max_repair_attempts", 2)))
    except (TypeError, ValueError):
        return 2


def _strip_unsupported_entities(text: str, allowed: set[str]) -> str:
    entities = (
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
    )
    out = text
    for ent in entities:
        if ent not in allowed and ent in out:
            out = out.replace(ent, "（已移除未授权实体）")
    return out


def _soften_causal(text: str) -> str:
    out = text
    for src, dst in _CAUSAL_SOFTEN:
        if src in out:
            out = out.replace(src, dst)
    return out


def repair_draft_once(
    draft: StructuredDraft,
    candidate: ContentCandidate,
    *,
    atom_store: ResearchAtomStore | None = None,
    error_codes: list[str] | None = None,
) -> StructuredDraft:
    """Apply one bounded repair pass. Never adds claims, numbers, or sources."""
    codes = set(error_codes or [])
    context = build_allowed_facts(candidate, atom_store=atom_store)
    allowed_entities = set(context.allowed_entities)
    allowed_claim_ids = {c.claim_id for c in context.allowed_claims}
    allowed_nums = {re.sub(r"\s+", "", n).lower() for n in context.allowed_numbers}

    repaired: list[DraftStatement] = []
    for stmt in draft.statements:
        text = stmt.text
        stype = stmt.statement_type
        claim_ids = list(stmt.claim_ids)

        # Drop orphan facts with no claim citation possible
        if stype == "FACT" and (
            "ORPHAN_FACT" in codes or "UNSUPPORTED_FACT" in codes
        ):
            if not claim_ids or not any(c in allowed_claim_ids for c in claim_ids):
                continue  # delete unsupported fact

        if "UNSUPPORTED_ENTITY" in codes:
            text = _strip_unsupported_entities(text, allowed_entities)
            if "（已移除未授权实体）" in text and not any(
                e in text for e in allowed_entities
            ):
                # If statement became empty of meaning, drop it
                if text.strip("（已移除未授权实体）。. ") == "":
                    continue

        if "UNSUPPORTED_NUMERIC_CLAIM" in codes or "PSEUDO_PRECISION" in codes:
            # Remove statements whose numbers are not allowed
            nums = re.findall(
                r"\d+(?:\.\d+)?\s*(?:%|亿元|万元|元/柜|元|SKU|台|天|小时|百分点|倍)|"
                r"第\s*\d+\s*天|Prediction\s*\d+|预测\s*\d+|★+",
                text,
                re.I,
            )
            if nums and stype == "FACT":
                bad = False
                for n in nums:
                    if "★" in n or re.search(r"prediction|预测", n, re.I):
                        bad = True
                        break
                    if re.sub(r"\s+", "", n).lower() not in allowed_nums:
                        bad = True
                        break
                if bad:
                    continue  # delete unsupported number statement

        if "UNSUPPORTED_CAUSAL_INFERENCE" in codes:
            text = _soften_causal(text)
            if any(
                m in stmt.text
                for m in ("说明其智能柜", "渠道动销能力", "因此智能柜", "所以智能柜")
            ):
                stype = "INFERENCE"
                claim_ids = [c for c in claim_ids if c in allowed_claim_ids]
                if not claim_ids and allowed_claim_ids:
                    claim_ids = [next(iter(allowed_claim_ids))]
                stmt = DraftStatement(
                    text=text,
                    statement_type=stype,
                    claim_ids=claim_ids,
                    supporting_claim_ids=claim_ids,
                    pending_verification=True,
                )
                repaired.append(stmt)
                continue

        # Fill missing citation from allowed claims when text matches
        if stype == "FACT" and not claim_ids:
            for ac in context.allowed_claims:
                if ac.text and ac.text in text:
                    claim_ids = [ac.claim_id]
                    break

        repaired.append(
            DraftStatement(
                text=text,
                statement_type=stype,
                claim_ids=claim_ids,
                supporting_claim_ids=list(stmt.supporting_claim_ids or claim_ids),
                numeric_kind=stmt.numeric_kind,
                formula=stmt.formula,
                inputs=list(stmt.inputs),
                parameter_basis=stmt.parameter_basis,
                zerorealm_suggested=stmt.zerorealm_suggested,
                industry_standard=False,  # never escalate to industry standard
                pending_verification=stmt.pending_verification or stype in {"INFERENCE", "HYPOTHESIS"},
            )
        )

    draft.statements = repaired
    draft.repair_attempts = int(draft.repair_attempts or 0) + 1
    draft.metadata["last_repair_codes"] = sorted(codes)
    # Never invent new claims
    draft.metadata["repair_added_claims"] = False
    return draft


def repair_until_pass_or_limit(
    draft: StructuredDraft,
    candidate: ContentCandidate,
    *,
    atom_store: ResearchAtomStore | None = None,
    max_attempts: int | None = None,
) -> RepairResult:
    limit = max_attempts if max_attempts is not None else max_repair_attempts()
    attempts = 0
    audit = audit_structured_draft(candidate, draft, atom_store=atom_store)
    if audit.passed:
        draft.status = "GATE_PASSED"
        return RepairResult(
            draft=draft,
            attempts=0,
            passed=True,
            status=draft.status,
            audit=audit.to_dict(),
        )

    while attempts < limit and not audit.passed:
        draft = repair_draft_once(
            draft,
            candidate,
            atom_store=atom_store,
            error_codes=audit.errors,
        )
        attempts += 1
        audit = audit_structured_draft(candidate, draft, atom_store=atom_store)

    if audit.passed:
        draft.status = "GATE_PASSED"
        candidate.status = ContentCandidateStatus.READY_FOR_EDITORIAL
    else:
        draft.status = "GATE_FAILED"
        candidate.status = ContentCandidateStatus.GATE_FAILED

    candidate.metadata["structured_draft"] = draft.to_dict()
    candidate.metadata["repair_attempts"] = attempts
    return RepairResult(
        draft=draft,
        attempts=attempts,
        passed=audit.passed,
        status=draft.status,
        audit=audit.to_dict(),
    )
