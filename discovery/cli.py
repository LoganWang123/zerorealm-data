"""CLI for Source Discovery (independent of main.py production crawl)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow `python discovery/cli.py` and `python -m discovery.cli` from repo root.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from discovery.pipeline import DiscoveryPipeline, DiscoveryPipelineConfig
from discovery.pool import CandidatePool
from discovery.providers.anysearch import AnySearchProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="discover",
        description="AnySearch Source Discovery → Fetch → Research Verify (stops before Daily/Publish)",
    )
    parser.add_argument("--query", required=True, help="Search query, e.g. 智能柜")
    parser.add_argument("--limit", type=int, default=5, help="Max search results (1-10)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover only: no fetch/verify, no durable pool write",
    )
    parser.add_argument(
        "--stage",
        choices=("discover", "fetch", "verify"),
        default="verify",
        help="Stop after stage (ignored when --dry-run)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Write candidate pool JSON under data/candidates/",
    )
    parser.add_argument(
        "--pool-path",
        default="data/candidates/pool.json",
        help="Candidate pool output path when --persist",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    enabled = os.getenv("ANYSEARCH_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        print(json.dumps({"ok": False, "error": "ANYSEARCH_ENABLED=false"}, ensure_ascii=False))
        return 2

    dry_run = bool(args.dry_run)
    stage = "discover" if dry_run else args.stage
    config = DiscoveryPipelineConfig(
        fetch=stage in {"fetch", "verify"},
        verify=stage == "verify",
        persist=bool(args.persist) and not dry_run,
        pool_path=args.pool_path,
    )
    pipeline = DiscoveryPipeline(
        provider=AnySearchProvider(),
        pool=CandidatePool(),
        config=config,
    )
    records = pipeline.run(args.query, limit=max(1, min(args.limit, 10)))
    payload = {
        "ok": True,
        "query": args.query,
        "dry_run": dry_run,
        "stage": stage,
        "api_key_configured": bool(os.getenv("ANYSEARCH_API_KEY", "").strip()),
        "count": len(records),
        "results": [r.to_dict() for r in records],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
