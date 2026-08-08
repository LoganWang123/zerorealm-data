#!/usr/bin/env python
"""Human Claim Review CLI (separate from Discovery triage queue).

Queue APPROVED ≠ ClaimStatus.VERIFIED.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from research.atom_store import DEFAULT_ATOMS_PATH, ResearchAtomStore
from research.claim_review import (
    ClaimReviewError,
    claim_review_payload,
    set_claim_status,
)
from research.exporters.verified_research import DEFAULT_EXPORT_PATH, export_verified_research
from research.models import ClaimStatus

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research_review",
        description="Human Claim Review + Verified Research Export (no Daily/Publish)",
    )
    parser.add_argument("--atoms-path", default=str(DEFAULT_ATOMS_PATH))
    parser.add_argument("--log-path", default="data/state/research_review_log.jsonl")
    parser.add_argument("--claim", metavar="ID", help="Show claim review payload")
    parser.add_argument("--verify-claim", metavar="ID", help="Set ClaimStatus.VERIFIED")
    parser.add_argument("--reject-claim", metavar="ID", help="Set ClaimStatus.REJECTED")
    parser.add_argument("--reviewer", default=None, help="Human reviewer identity")
    parser.add_argument("--reason", default="", help="Review reason")
    parser.add_argument(
        "--export-verified",
        action="store_true",
        help="Export ClaimStatus.VERIFIED claims only",
    )
    parser.add_argument(
        "--export-knowledge",
        action="store_true",
        help="Sync VERIFIED claims into Knowledge store",
    )
    parser.add_argument("--export-path", default=str(DEFAULT_EXPORT_PATH))
    parser.add_argument(
        "--persist",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def _emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8", errors="replace"))
        stream.flush()
        return
    print(text, end="")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ResearchAtomStore.load_or_create(args.atoms_path)

    try:
        if args.export_verified:
            payload = export_verified_research(
                store=store,
                atoms_path=args.atoms_path,
                output_path=args.export_path,
            )
            _emit({"ok": True, "mode": "export-verified", "export_path": args.export_path, **payload})
            return 0

        if args.export_knowledge:
            from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms

            knowledge = KnowledgeStore.load_or_create("data/state/knowledge_store.json")
            rows = sync_knowledge_from_atoms(
                atom_store=store,
                knowledge_store=knowledge,
                persist=args.persist,
            )
            _emit(
                {
                    "ok": True,
                    "mode": "export-knowledge",
                    "count": len(rows),
                    "active": sum(1 for r in rows if r.status.value == "active"),
                }
            )
            return 0

        if args.claim:
            payload = claim_review_payload(store, args.claim)
            _emit({"ok": True, "mode": "claim", "item": payload})
            return 0

        if args.verify_claim:
            claim = set_claim_status(
                store,
                args.verify_claim,
                ClaimStatus.VERIFIED,
                reviewer=args.reviewer,
                reason=args.reason,
                log_path=args.log_path,
                persist=args.persist,
            )
            _emit(
                {
                    "ok": True,
                    "mode": "verify-claim",
                    "claim_id": claim.id,
                    "status": claim.status.value,
                    "reviewed_at": claim.reviewed_at,
                    "note": "ClaimStatus.VERIFIED set by explicit human reviewer only.",
                }
            )
            return 0

        if args.reject_claim:
            claim = set_claim_status(
                store,
                args.reject_claim,
                ClaimStatus.REJECTED,
                reviewer=args.reviewer,
                reason=args.reason,
                log_path=args.log_path,
                persist=args.persist,
            )
            _emit(
                {
                    "ok": True,
                    "mode": "reject-claim",
                    "claim_id": claim.id,
                    "status": claim.status.value,
                    "reviewed_at": claim.reviewed_at,
                }
            )
            return 0
    except ClaimReviewError as exc:
        _emit({"ok": False, "error_code": exc.code, "error": exc.message})
        return 2

    _emit(
        {
            "ok": False,
            "error": "Provide --claim / --verify-claim / --reject-claim / --export-verified",
        }
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
