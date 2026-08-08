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
from discovery.pool import DEFAULT_POOL_PATH, CandidatePool
from discovery.providers.anysearch import AnySearchProvider
from discovery.queries import resolve_queries

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="discover",
        description="AnySearch Source Discovery → Fetch → Research Verify (stops before Daily/Publish)",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query", help="Direct search query, e.g. 智能柜")
    source.add_argument("--topic", help="Topic key from config/source_queries.yaml")
    source.add_argument("--company", help="Company name expanded via registry templates")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max search results per query (1-10)",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Override registry max_queries_per_run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover only: no fetch/verify; still can report candidates",
    )
    parser.add_argument(
        "--stage",
        choices=("discover", "fetch", "verify"),
        default="verify",
        help="Stop after stage (ignored when --dry-run)",
    )
    parser.add_argument(
        "--persist",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist durable candidate pool (default: on; disabled for --dry-run)",
    )
    parser.add_argument(
        "--pool-path",
        default=str(DEFAULT_POOL_PATH),
        help="Durable candidate pool path (default: data/state/candidate_pool.json)",
    )
    parser.add_argument(
        "--registry",
        default="config/source_queries.yaml",
        help="Query registry YAML path",
    )
    return parser


def _emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8", errors="replace"))
        stream.flush()
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    print(text, end="")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    enabled = os.getenv("ANYSEARCH_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        _emit({"ok": False, "error": "ANYSEARCH_ENABLED=false"})
        return 2

    try:
        plan = resolve_queries(
            query=args.query,
            topic=args.topic,
            company=args.company,
            registry_path=args.registry,
            max_queries=args.max_queries,
        )
    except (ValueError, KeyError, FileNotFoundError) as exc:
        _emit({"ok": False, "error": str(exc)})
        return 2

    dry_run = bool(args.dry_run)
    stage = "discover" if dry_run else args.stage
    persist = bool(args.persist) and not dry_run
    config = DiscoveryPipelineConfig(
        fetch=stage in {"fetch", "verify"},
        verify=stage == "verify",
        persist=persist,
        pool_path=args.pool_path,
        results_per_query=max(1, min(args.limit, 10)),
    )
    pool = CandidatePool.load_or_create(args.pool_path) if persist or not dry_run else CandidatePool(args.pool_path)
    if not persist and dry_run:
        # dry-run starts empty in-memory unless pool already loaded for inspection
        pool = CandidatePool(args.pool_path)

    pipeline = DiscoveryPipeline(
        provider=AnySearchProvider(),
        pool=pool,
        config=config,
    )
    summary = pipeline.run_queries(plan.queries, results_per_query=config.results_per_query)
    payload = {
        "ok": True,
        "mode": plan.mode,
        "label": plan.label,
        "queries": plan.queries,
        "max_queries_per_run": plan.max_queries_per_run,
        "dry_run": dry_run,
        "stage": stage,
        "api_key_configured": bool(os.getenv("ANYSEARCH_API_KEY", "").strip()),
        "search_results": summary.search_results,
        "deduped": summary.deduped,
        "count": len(summary.records),
        "pool_path": args.pool_path if persist else None,
        "results": [r.to_dict() for r in summary.records],
    }
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
