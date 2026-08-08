#!/usr/bin/env python
"""Release Orchestrator CLI — preflight / status / plan / dry-run (no real publish)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
        description="Release Orchestrator: status / preflight / plan / dry-run (no publish)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "preflight", "plan", "dry-run"):
        p = sub.add_parser(name)
        p.add_argument("rc_id", help="release_candidate_id or content_id")
        p.add_argument("--rc-path", default=None)
        if name == "dry-run":
            p.add_argument("--out-dir", default=None)
    model = sub.add_parser("partial-model", help="Show PARTIALLY_PUBLISHED recovery model")
    del model  # silence unused in some linters
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
    if args.command == "partial-model":
        _emit({"ok": True, "mode": "partial-model", "model": partial_publish_model_example()})
        return 0

    cfg = load_content_config()
    paths = cfg.get("paths") or {}
    rc_path = args.rc_path or paths.get("release_candidates") or "data/state/release_candidates.json"
    store = ReleaseCandidateStore.load_or_create(rc_path)
    rc = store.get(args.rc_id) or store.get_by_content_id(args.rc_id)
    if rc is None:
        _emit({"ok": False, "error": f"Unknown release candidate: {args.rc_id}"})
        return 2

    orch = ReleaseOrchestrator()
    try:
        if args.command == "status":
            status = orch.status(rc)
            _emit({"ok": True, "mode": "status", "status": status.to_dict()})
            return 0
        if args.command == "preflight":
            status = orch.preflight(rc, write_plans=False)
            store.upsert(rc)
            # Do not persist by default — callers using durable store should save explicitly.
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
    except ReleaseCandidateError as exc:
        _emit({"ok": False, "error_code": exc.code, "error": exc.message})
        return 2

    _emit({"ok": False, "error": "Unknown command"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
