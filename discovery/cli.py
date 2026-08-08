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
from discovery.review_queue import DEFAULT_QUEUE_PATH, ResearchReviewQueue, ReviewStatus

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="discover",
        description=(
            "AnySearch Source Discovery → Fetch → Research Verify → Review Queue "
            "(stops before Daily/Publish)"
        ),
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--query", help="Direct search query, e.g. 智能柜")
    source.add_argument("--topic", help="Topic key from config/source_queries.yaml")
    source.add_argument("--company", help="Company name expanded via registry templates")
    source.add_argument(
        "--review-queue",
        action="store_true",
        help="List PENDING research review queue items",
    )
    source.add_argument("--review", metavar="ID", help="Show one review queue item")
    source.add_argument("--approve", metavar="ID", help="Approve a review queue item")
    source.add_argument("--reject", metavar="ID", help="Reject a review queue item")
    source.add_argument("--defer", metavar="ID", help="Defer a review queue item")
    parser.add_argument(
        "--reason",
        default="",
        help="Optional review reason for --approve/--reject/--defer",
    )
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
        help="Persist durable candidate pool / review queue (default: on; disabled for --dry-run)",
    )
    parser.add_argument(
        "--pool-path",
        default=str(DEFAULT_POOL_PATH),
        help="Durable candidate pool path (default: data/state/candidate_pool.json)",
    )
    parser.add_argument(
        "--queue-path",
        default=str(DEFAULT_QUEUE_PATH),
        help="Durable research review queue path",
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


def _review_summary(item) -> dict:
    return {
        "queue_item_id": item.queue_item_id,
        "candidate_id": item.candidate_id,
        "title": item.title,
        "publisher": item.publisher,
        "source_type": item.source_type,
        "source_tier": item.source_tier,
        "published_at": item.published_at,
        "freshness_score": item.freshness_score,
        "discovery_score": item.discovery_score,
        "url": item.url,
        "query": item.query,
        "provider": item.provider,
        "review_status": item.review_status.value,
        "review_reason": item.review_reason,
        "created_at": item.created_at,
    }


def _handle_review_commands(args) -> int:
    queue = ResearchReviewQueue.load_or_create(args.queue_path)
    if args.review_queue:
        pending = queue.list_pending()
        _emit(
            {
                "ok": True,
                "mode": "review-queue",
                "count": len(pending),
                "queue_path": args.queue_path,
                "items": [_review_summary(i) for i in pending],
            }
        )
        return 0

    target_id = args.review or args.approve or args.reject or args.defer
    item = queue.get(target_id) or queue.get_by_candidate(target_id)
    if item is None:
        _emit({"ok": False, "error": f"Review item not found: {target_id}"})
        return 2

    if args.review:
        _emit({"ok": True, "mode": "review", "item": item.to_dict()})
        return 0

    if args.approve:
        status = ReviewStatus.APPROVED
    elif args.reject:
        status = ReviewStatus.REJECTED
    else:
        status = ReviewStatus.DEFERRED

    updated = queue.set_status(item.queue_item_id, status, reason=args.reason or "")
    if args.persist:
        queue.save(args.queue_path)
    _emit(
        {
            "ok": True,
            "mode": status.value.lower(),
            "item": _review_summary(updated) if updated else None,
            "note": (
                "APPROVED means human accepted this item into formal research review; "
                "ClaimStatus is not auto-upgraded to verified."
            ),
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    review_mode = any(
        [args.review_queue, args.review, args.approve, args.reject, args.defer]
    )
    discover_mode = any([args.query, args.topic, args.company])
    if review_mode and discover_mode:
        _emit({"ok": False, "error": "Do not mix discovery flags with review flags"})
        return 2
    if not review_mode and not discover_mode:
        _emit(
            {
                "ok": False,
                "error": "Provide --query/--topic/--company or a review command",
            }
        )
        return 2
    if review_mode:
        return _handle_review_commands(args)

    enabled = os.getenv("ANYSEARCH_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }
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
    limit = max(1, min(args.limit, 10))
    if plan.max_results:
        limit = max(1, min(limit, int(plan.max_results)))

    config = DiscoveryPipelineConfig(
        fetch=stage in {"fetch", "verify"},
        verify=stage == "verify",
        persist=persist,
        pool_path=args.pool_path,
        queue_path=args.queue_path,
        results_per_query=limit,
        intent=plan.intent,
        freshness_window=plan.freshness_window,
        topic_terms=list(plan.topic_terms),
        company_terms=list(plan.company_terms),
    )
    if persist or not dry_run:
        pool = CandidatePool.load_or_create(args.pool_path)
        queue = ResearchReviewQueue.load_or_create(args.queue_path)
    else:
        pool = CandidatePool(args.pool_path)
        queue = ResearchReviewQueue(args.queue_path)

    pipeline = DiscoveryPipeline(
        provider=AnySearchProvider(),
        pool=pool,
        review_queue=queue,
        config=config,
    )
    summary = pipeline.run_queries(plan.queries, results_per_query=config.results_per_query)
    payload = {
        "ok": True,
        "mode": plan.mode,
        "label": plan.label,
        "queries": plan.queries,
        "intent": plan.intent,
        "freshness_window": plan.freshness_window,
        "max_queries_per_run": plan.max_queries_per_run,
        "dry_run": dry_run,
        "stage": stage,
        "api_key_configured": bool(os.getenv("ANYSEARCH_API_KEY", "").strip()),
        "search_results": summary.search_results,
        "deduped": summary.deduped,
        "count": len(summary.records),
        "queue_enqueued": summary.queue_enqueued,
        "pool_path": args.pool_path if persist else None,
        "queue_path": args.queue_path if persist else None,
        "results": [r.to_dict() for r in summary.records],
    }
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
