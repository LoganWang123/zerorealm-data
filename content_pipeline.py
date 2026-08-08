#!/usr/bin/env python
"""Content pipeline CLI: Knowledge → Candidate → Gate → Editorial → Package.

Stops before WeChat/Website publish.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from content.brief import build_editorial_brief, build_internal_draft, write_review_draft
from content.candidates import build_candidates
from content.editorial_review import set_editorial_status
from content.gate import run_content_hard_gate
from content.models import ContentType, EditorialStatus
from content.package import PackageError, build_publish_ready_package, save_package
from content.store import ContentCandidateStore, load_content_config
from research.atom_store import ResearchAtomStore
from research.claim_review import ClaimReviewError
from research.knowledge import KnowledgeStore, sync_knowledge_from_atoms

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content_pipeline",
        description="Verified Knowledge → Content Candidate → Gate → Editorial → Package (no publish)",
    )
    parser.add_argument("--export-knowledge", action="store_true")
    parser.add_argument("--build-candidates", action="store_true")
    parser.add_argument("--type", choices=("daily", "insight"), default="daily")
    parser.add_argument("--knowledge-ids", default="", help="Comma-separated knowledge ids")
    parser.add_argument("--topic", default="")
    parser.add_argument("--list-candidates", action="store_true")
    parser.add_argument("--show", metavar="ID")
    parser.add_argument("--brief", metavar="ID")
    parser.add_argument("--draft", metavar="ID")
    parser.add_argument("--gate", metavar="ID")
    parser.add_argument("--approve", metavar="ID")
    parser.add_argument("--reject", metavar="ID")
    parser.add_argument("--needs-edit", metavar="ID")
    parser.add_argument("--build-package", metavar="ID")
    parser.add_argument("--reviewer", default=None)
    parser.add_argument("--reason", default="")
    parser.add_argument("--atoms-path", default=None)
    parser.add_argument("--knowledge-path", default=None)
    parser.add_argument("--candidates-path", default=None)
    parser.add_argument("--persist", action=argparse.BooleanOptionalAction, default=True)
    return parser


def _emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8", errors="replace"))
        stream.flush()
        return
    print(text, end="")


def _paths(args):
    cfg = load_content_config()
    paths = cfg.get("paths") or {}
    return {
        "atoms": args.atoms_path or "data/state/research_atoms.json",
        "knowledge": args.knowledge_path or paths.get("knowledge") or "data/state/knowledge_store.json",
        "candidates": args.candidates_path
        or paths.get("candidates")
        or "data/state/content_candidates.json",
        "packages": paths.get("packages") or "data/state/publish_ready_packages.json",
        "editorial_log": paths.get("editorial_log") or "data/state/editorial_review_log.jsonl",
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = _paths(args)
    try:
        if args.export_knowledge:
            atoms = ResearchAtomStore.load_or_create(paths["atoms"])
            knowledge = KnowledgeStore.load_or_create(paths["knowledge"])
            rows = sync_knowledge_from_atoms(
                atom_store=atoms,
                knowledge_store=knowledge,
                persist=args.persist,
            )
            _emit(
                {
                    "ok": True,
                    "mode": "export-knowledge",
                    "count": len(rows),
                    "active": sum(1 for r in rows if r.status.value == "active"),
                    "path": paths["knowledge"],
                    "records": [r.to_dict() for r in rows],
                }
            )
            return 0

        knowledge = KnowledgeStore.load_or_create(paths["knowledge"])
        store = ContentCandidateStore.load_or_create(paths["candidates"])
        atoms = ResearchAtomStore.load_or_create(paths["atoms"])

        if args.build_candidates:
            kids = [x.strip() for x in args.knowledge_ids.split(",") if x.strip()]
            built = build_candidates(
                knowledge_store=knowledge,
                candidate_store=store,
                content_type=ContentType(args.type),
                knowledge_ids=kids or None,
                topic=args.topic,
                persist=args.persist,
            )
            for cand in built:
                build_editorial_brief(cand)
                build_internal_draft(cand)
                store.upsert(cand)
            if args.persist:
                store.save()
            _emit(
                {
                    "ok": True,
                    "mode": "build-candidates",
                    "count": len(built),
                    "ids": [c.content_candidate_id for c in built],
                }
            )
            return 0

        if args.list_candidates:
            rows = store.all()
            _emit(
                {
                    "ok": True,
                    "mode": "list-candidates",
                    "count": len(rows),
                    "items": [
                        {
                            "id": c.content_candidate_id,
                            "type": c.content_type.value,
                            "status": c.status.value,
                            "editorial": c.editorial_status.value,
                            "title": c.primary_signal,
                            "content_id": c.content_id,
                        }
                        for c in rows
                    ],
                }
            )
            return 0

        target_id = (
            args.show
            or args.brief
            or args.draft
            or args.gate
            or args.approve
            or args.reject
            or args.needs_edit
            or args.build_package
        )
        if target_id:
            cand = store.get(target_id)
            if cand is None:
                _emit({"ok": False, "error": f"Unknown candidate: {target_id}"})
                return 2

            if args.show:
                _emit({"ok": True, "mode": "show", "item": cand.to_dict()})
                return 0
            if args.brief:
                brief = build_editorial_brief(cand)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit({"ok": True, "mode": "brief", "brief": brief})
                return 0
            if args.draft:
                draft = build_internal_draft(cand)
                path = write_review_draft(cand)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit({"ok": True, "mode": "draft", "path": str(path), "draft": draft})
                return 0
            if args.gate:
                result = run_content_hard_gate(cand, atom_store=atoms)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit(
                    {
                        "ok": True,
                        "mode": "gate",
                        "passed": result.passed,
                        "gate_result": cand.gate_result,
                        "status": cand.status.value,
                    }
                )
                return 0
            if args.approve or args.reject or args.needs_edit:
                if args.approve:
                    status = EditorialStatus.APPROVED
                elif args.reject:
                    status = EditorialStatus.REJECTED
                else:
                    status = EditorialStatus.NEEDS_EDIT
                set_editorial_status(
                    cand,
                    status,
                    reviewer=args.reviewer,
                    reason=args.reason,
                    log_path=paths["editorial_log"],
                )
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit(
                    {
                        "ok": True,
                        "mode": status.value.lower(),
                        "editorial_status": cand.editorial_status.value,
                        "candidate_status": cand.status.value,
                    }
                )
                return 0
            if args.build_package:
                package = build_publish_ready_package(cand)
                if args.persist:
                    save_package(package, path=paths["packages"])
                    store.upsert(cand)
                    store.save()
                _emit(
                    {
                        "ok": True,
                        "mode": "build-package",
                        "package": package,
                        "wechat_published": False,
                        "website_published": False,
                    }
                )
                return 0

    except (ClaimReviewError, PackageError, ValueError) as exc:
        code = getattr(exc, "code", "ERROR")
        message = getattr(exc, "message", str(exc))
        _emit({"ok": False, "error_code": code, "error": message})
        return 2

    _emit({"ok": False, "error": "No action specified. See --help."})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
