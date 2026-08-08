#!/usr/bin/env python
"""Release CLI — orchestrator + controlled publisher (default: no real side effects)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from content.controlled_publish.confirmation import build_confirmation_token
from content.controlled_publish.errors import ControlledPublishError
from content.controlled_publish.modes import ExecutionMode, publish_disabled
from content.controlled_publish.service import ControlledPublishService
from content.orchestrator import ReleaseOrchestrator, partial_publish_model_example
from content.release_candidate import ReleaseCandidateError, ReleaseCandidateStore
from content.store import load_content_config

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release",
        description="Release Orchestrator + Controlled Publisher (PUBLISH_DISABLED by default)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "preflight", "plan", "dry-run"):
        p = sub.add_parser(name)
        p.add_argument("rc_id", help="release_candidate_id or content_id")
        p.add_argument("--rc-path", default=None)
        if name == "dry-run":
            p.add_argument("--out-dir", default=None)

    sub.add_parser("partial-model", help="Show PARTIALLY_PUBLISHED recovery model")

    p = sub.add_parser("confirmation-token", help="Generate confirmation token for RC")
    p.add_argument("rc_id")
    p.add_argument("--rc-path", default=None)

    p = sub.add_parser("publish", help="Controlled publish (blocked unless kill switch off + confirm)")
    p.add_argument("rc_id")
    p.add_argument("--rc-path", default=None)
    p.add_argument("--mode", default=ExecutionMode.DRY_RUN.value, choices=[m.value for m in ExecutionMode])
    p.add_argument("--confirm", default=None, help="CONFIRM-XXXXXX")
    p.add_argument("--freepublish-approved", action="store_true", default=False)
    p.add_argument("--channel", action="append", dest="channels", default=None)
    p.add_argument("--state-root", default=None)

    p = sub.add_parser("transaction", help="Show publish transaction")
    p.add_argument("transaction_id")
    p.add_argument("--state-root", default=None)

    p = sub.add_parser("retry", help="Retry failed channel only")
    p.add_argument("transaction_id")
    p.add_argument("--channel", required=True, choices=("website", "wechat"))
    p.add_argument("rc_id")
    p.add_argument("--rc-path", default=None)
    p.add_argument("--confirm", default=None)
    p.add_argument("--freepublish-approved", action="store_true", default=False)
    p.add_argument("--state-root", default=None)

    p = sub.add_parser("recovery-plan", help="Build recovery plan for transaction")
    p.add_argument("transaction_id")
    p.add_argument("--state-root", default=None)

    p = sub.add_parser("receipts", help="List receipts for RC")
    p.add_argument("rc_id")
    p.add_argument("--state-root", default=None)

    p = sub.add_parser("lock-status", help="Show release lock status")
    p.add_argument("rc_id")
    p.add_argument("--state-root", default=None)

    return parser


def _emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8", errors="replace"))
        stream.flush()
        return
    print(text, end="")


def _service(state_root: str | None) -> ControlledPublishService:
    root = state_root or "data/state/controlled_publish"
    return ControlledPublishService(root=root)


def _load_rc(args):
    cfg = load_content_config()
    paths = cfg.get("paths") or {}
    rc_path = getattr(args, "rc_path", None) or paths.get("release_candidates") or "data/state/release_candidates.json"
    store = ReleaseCandidateStore.load_or_create(rc_path)
    rc = store.get(args.rc_id) or store.get_by_content_id(args.rc_id)
    return store, rc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "partial-model":
        _emit({"ok": True, "mode": "partial-model", "model": partial_publish_model_example()})
        return 0

    if args.command in ("transaction", "recovery-plan", "receipts", "lock-status"):
        svc = _service(getattr(args, "state_root", None))
        try:
            if args.command == "transaction":
                txn = svc.txn_store.get(args.transaction_id)
                if txn is None:
                    _emit({"ok": False, "error": "TRANSACTION_NOT_FOUND"})
                    return 2
                _emit({"ok": True, "transaction": txn.to_dict()})
                return 0
            if args.command == "recovery-plan":
                _emit({"ok": True, "plan": svc.recovery_plan(args.transaction_id)})
                return 0
            if args.command == "receipts":
                rows = [r.to_dict() for r in svc.receipt_store.list_for_rc(args.rc_id)]
                # rc_id arg may be content id — also accept as release_candidate_id prefix search
                _emit({"ok": True, "receipts": rows, "publish_disabled": publish_disabled()})
                return 0
            if args.command == "lock-status":
                lock = svc.lock_store.status(args.rc_id)
                _emit({"ok": True, "lock": lock.to_dict() if lock else None})
                return 0
        except ControlledPublishError as exc:
            _emit({"ok": False, "error_code": exc.code, "error": exc.message})
            return 2

    store, rc = _load_rc(args)
    if rc is None:
        _emit({"ok": False, "error": f"Unknown release candidate: {args.rc_id}"})
        return 2

    orch = ReleaseOrchestrator()
    svc = _service(getattr(args, "state_root", None))

    try:
        if args.command == "status":
            status = orch.status(rc)
            _emit({"ok": True, "mode": "status", "status": status.to_dict()})
            return 0
        if args.command == "preflight":
            status = orch.preflight(rc, write_plans=False)
            _emit({"ok": True, "mode": "preflight", "status": status.to_dict()})
            return 0 if status.ready else 2
        if args.command == "plan":
            plan = orch.plan(rc)
            _emit({"ok": True, "mode": "plan", **plan})
            return 0
        if args.command == "dry-run":
            out = orch.dry_run(rc, out_dir=args.out_dir)
            _emit({"ok": True, "mode": "dry-run", **out})
            return 0
        if args.command == "confirmation-token":
            token = build_confirmation_token(rc)
            _emit(
                {
                    "ok": True,
                    "confirmation_token": token,
                    "release_candidate_id": rc.release_candidate_id,
                    "revision": rc.revision,
                    "content_fingerprint": rc.content_fingerprint,
                    "note": "Token invalidates when revision/fingerprint change",
                }
            )
            return 0
        if args.command == "publish":
            # Always report kill switch; refuse PRODUCTION networking regardless of keys.
            result = svc.execute(
                rc,
                mode=args.mode,
                confirm=args.confirm,
                channels=args.channels,
                freepublish_approved=args.freepublish_approved,
            )
            _emit(
                {
                    "ok": bool(result.get("ok")),
                    "mode": "publish",
                    "publish_disabled": publish_disabled(),
                    **result,
                }
            )
            return 0 if result.get("ok") or args.mode == ExecutionMode.DRY_RUN.value else 2
        if args.command == "retry":
            result = svc.retry(
                args.transaction_id,
                rc,
                channel=args.channel,
                confirm=args.confirm,
                freepublish_approved=args.freepublish_approved,
            )
            _emit({"ok": bool(result.get("ok")), "mode": "retry", **result})
            return 0 if result.get("ok") or result.get("skipped") else 2
    except ReleaseCandidateError as exc:
        _emit({"ok": False, "error_code": exc.code, "error": exc.message})
        return 2
    except ControlledPublishError as exc:
        _emit({"ok": False, "error_code": exc.code, "error": exc.message})
        return 2

    _emit({"ok": False, "error": "Unknown command"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
