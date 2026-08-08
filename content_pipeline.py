#!/usr/bin/env python
"""Content pipeline CLI: Knowledge → Controlled Draft → Audit → Render → RC.

Stops before WeChat/Website publish.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from content.audit import audit_structured_draft
from content.brief import build_editorial_brief, build_internal_draft, write_review_draft
from content.candidates import build_candidates
from content.channel_render import RenderError, render_channels, render_website_preview, render_wechat_preview
from content.consistency import check_channel_consistency
from content.editorial_review import set_editorial_status
from content.gate import run_content_hard_gate
from content.generator import StructuredDraft, generate_controlled_draft, get_generator
from content.models import ContentType, EditorialStatus
from content.package import PackageError, build_publish_ready_package, save_package
from content.release_candidate import (
    ChannelReviewStatus,
    ReleaseCandidateError,
    ReleaseCandidateStore,
    assert_ready_for_publish,
    build_release_candidate,
    set_channel_review,
)
from content.publisher_preflight import publisher_invoke_guard
from content.repair import repair_until_pass_or_limit
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
        description=(
            "Verified Knowledge → Controlled Draft → Audit → Channel Preview → "
            "Release Candidate (no publish)"
        ),
    )
    parser.add_argument("--export-knowledge", action="store_true")
    parser.add_argument("--build-candidates", action="store_true")
    parser.add_argument("--type", choices=("daily", "insight"), default="daily")
    parser.add_argument("--knowledge-ids", default="", help="Comma-separated knowledge ids")
    parser.add_argument("--topic", default="")
    parser.add_argument("--list-candidates", action="store_true")
    parser.add_argument("--show", metavar="ID")
    parser.add_argument("--brief", metavar="ID")
    parser.add_argument("--draft", metavar="ID", help="Legacy internal draft builder")
    parser.add_argument("--generate", metavar="ID", help="Controlled generator from Allowed Facts")
    parser.add_argument(
        "--provider",
        default=None,
        help="Content generator provider: mock|deepseek (default CONTENT_GENERATOR_PROVIDER)",
    )
    parser.add_argument("--model", default=None, help="Override CONTENT_GENERATOR_MODEL / LLM_MODEL")
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Request live generation (still requires CONTENT_GENERATOR_ALLOW_LIVE=1)",
    )
    parser.add_argument("--audit-draft", metavar="ID", help="Post-generation claim audit")
    parser.add_argument("--repair", metavar="ID", help="Bounded repair + re-audit")
    parser.add_argument("--gate", metavar="ID")
    parser.add_argument("--approve", metavar="ID")
    parser.add_argument("--reject", metavar="ID")
    parser.add_argument("--needs-edit", metavar="ID")
    parser.add_argument("--build-package", metavar="ID")
    parser.add_argument("--render", metavar="ID", help="content_candidate_id or content_id")
    parser.add_argument("--channel", choices=("website", "wechat", "all"), default="all")
    parser.add_argument("--channel-check", metavar="ID")
    parser.add_argument("--release-candidate", metavar="ID")
    parser.add_argument("--show-release-candidate", metavar="ID")
    parser.add_argument("--channel-review", metavar="ID", help="release_candidate_id")
    parser.add_argument("--approve-channel", metavar="ID", help="Approve one channel review")
    parser.add_argument("--release-preflight", metavar="ID", help="Dry-run publish preflight")
    parser.add_argument("--publish-plan", metavar="ID", help="Alias of release-preflight dry-run")
    parser.add_argument(
        "--channel-review-status",
        choices=("APPROVED", "REJECTED", "NEEDS_EDIT", "PENDING"),
        default=None,
    )
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--corrupt", default=None, help="Mock generator corruption mode (tests)")
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
        "release_candidates": paths.get("release_candidates") or "data/state/release_candidates.json",
        "channel_review_log": paths.get("channel_review_log") or "data/state/channel_review_log.jsonl",
    }


def _resolve_candidate(store: ContentCandidateStore, target_id: str):
    cand = store.get(target_id)
    if cand is not None:
        return cand
    for row in store.all():
        if row.content_id == target_id:
            return row
    return None


def _structured_from_candidate(cand) -> StructuredDraft:
    raw = cand.metadata.get("structured_draft") or cand.draft or {}
    if isinstance(raw, StructuredDraft):
        return raw
    return StructuredDraft.from_dict(raw)


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
        rc_store = ReleaseCandidateStore.load_or_create(paths["release_candidates"])

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

        if args.show_release_candidate:
            rc = rc_store.get(args.show_release_candidate) or rc_store.get_by_content_id(
                args.show_release_candidate
            )
            if rc is None:
                _emit({"ok": False, "error": f"Unknown release candidate: {args.show_release_candidate}"})
                return 2
            _emit({"ok": True, "mode": "show-release-candidate", "item": rc.to_dict()})
            return 0

        if args.channel_review or args.approve_channel:
            target = args.channel_review or args.approve_channel
            rc = rc_store.get(target) or rc_store.get_by_content_id(target)
            if rc is None:
                _emit({"ok": False, "error": f"Unknown release candidate: {target}"})
                return 2
            if args.channel == "all":
                _emit({"ok": False, "error": "Require --channel website|wechat"})
                return 2
            if args.approve_channel:
                status = ChannelReviewStatus.APPROVED
            else:
                if not args.channel_review_status:
                    _emit(
                        {
                            "ok": False,
                            "error": "Require --channel-review-status",
                        }
                    )
                    return 2
                status = ChannelReviewStatus(args.channel_review_status)
            set_channel_review(
                rc,
                args.channel,
                status,
                reviewer=args.reviewer,
                reason=args.reason,
                log_path=paths["channel_review_log"],
            )
            rc_store.upsert(rc)
            if args.persist:
                rc_store.save()
            publish_blocked = True
            try:
                assert_ready_for_publish(rc)
                publish_blocked = False
            except ReleaseCandidateError:
                publish_blocked = True
            _emit(
                {
                    "ok": True,
                    "mode": "channel-review",
                    "status": rc.status.value,
                    "website_review": rc.website_review,
                    "wechat_review": rc.wechat_review,
                    "publisher_blocked": publish_blocked,
                }
            )
            return 0

        if args.release_preflight or args.publish_plan:
            target = args.release_preflight or args.publish_plan
            rc = rc_store.get(target) or rc_store.get_by_content_id(target)
            if rc is None:
                _emit({"ok": False, "error": f"Unknown release candidate: {target}"})
                return 2
            if not args.dry_run:
                _emit(
                    {
                        "ok": False,
                        "error_code": "PUBLISH_DISABLED",
                        "error": "Real publish disabled; use --dry-run",
                    }
                )
                return 2
            plan = publisher_invoke_guard(rc, dry_run=True)
            _emit(
                {
                    "ok": True,
                    "mode": "release-preflight",
                    "dry_run": True,
                    "plan": plan,
                    "wechat_api_called": False,
                    "website_production_written": False,
                }
            )
            return 0

        target_id = (
            args.show
            or args.brief
            or args.draft
            or args.generate
            or args.audit_draft
            or args.repair
            or args.gate
            or args.approve
            or args.reject
            or args.needs_edit
            or args.build_package
            or args.render
            or args.channel_check
            or args.release_candidate
        )
        if target_id:
            cand = _resolve_candidate(store, target_id)
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
            if args.generate:
                if args.live and os.getenv("CONTENT_GENERATOR_ALLOW_LIVE") != "1":
                    _emit(
                        {
                            "ok": False,
                            "error_code": "LIVE_GENERATOR_DISABLED",
                            "error": "--live requires CONTENT_GENERATOR_ALLOW_LIVE=1",
                        }
                    )
                    return 2
                provider = args.provider or os.getenv("CONTENT_GENERATOR_PROVIDER") or "mock"
                structured = generate_controlled_draft(
                    cand,
                    atom_store=atoms,
                    generator=get_generator(
                        provider=provider,
                        corrupt=args.corrupt,
                        model=args.model,
                    ),
                    corrupt=args.corrupt,
                    provider=provider,
                    model=args.model,
                )
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit(
                    {
                        "ok": True,
                        "mode": "generate",
                        "provider": structured.generator_provider,
                        "draft_id": structured.draft_id,
                        "draft": structured.to_dict(),
                        "allowed_facts": cand.metadata.get("allowed_facts"),
                    }
                )
                return 0
            if args.audit_draft:
                structured = _structured_from_candidate(cand)
                report = audit_structured_draft(cand, structured, atom_store=atoms)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit(
                    {
                        "ok": True,
                        "mode": "audit-draft",
                        "passed": report.passed,
                        "audit": report.to_dict(),
                        "status": cand.status.value,
                    }
                )
                return 0
            if args.repair:
                structured = _structured_from_candidate(cand)
                result = repair_until_pass_or_limit(structured, cand, atom_store=atoms)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit(
                    {
                        "ok": True,
                        "mode": "repair",
                        "passed": result.passed,
                        "attempts": result.attempts,
                        "status": result.status,
                        "audit": result.audit,
                    }
                )
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
            if args.render:
                if args.channel == "website":
                    out = {"website": render_website_preview(cand), "publisher_invoked": False}
                elif args.channel == "wechat":
                    out = {"wechat": render_wechat_preview(cand), "publisher_invoked": False}
                else:
                    out = render_channels(cand)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit({"ok": True, "mode": "render", "channel": args.channel, **out})
                return 0
            if args.channel_check:
                report = check_channel_consistency(cand)
                store.upsert(cand)
                if args.persist:
                    store.save()
                _emit({"ok": True, "mode": "channel-check", "report": report.to_dict()})
                return 0
            if args.release_candidate:
                rc = build_release_candidate(cand)
                rc_store.upsert(rc)
                store.upsert(cand)
                if args.persist:
                    rc_store.save()
                    store.save()
                # Ensure publisher would be rejected at this status
                publish_error = None
                try:
                    assert_ready_for_publish(rc)
                except ReleaseCandidateError as exc:
                    publish_error = {"code": exc.code, "message": exc.message}
                _emit(
                    {
                        "ok": True,
                        "mode": "release-candidate",
                        "release_candidate": rc.to_dict(),
                        "wechat_published": False,
                        "website_published": False,
                        "publisher_precondition": publish_error,
                    }
                )
                return 0

    except (
        ClaimReviewError,
        PackageError,
        RenderError,
        ReleaseCandidateError,
        ValueError,
    ) as exc:
        code = getattr(exc, "code", "ERROR")
        message = getattr(exc, "message", str(exc))
        _emit({"ok": False, "error_code": code, "error": message})
        return 2

    _emit({"ok": False, "error": "No action specified. See --help."})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
