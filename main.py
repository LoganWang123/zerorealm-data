"""ZeroRealm Data Crawler - CLI Entry Point."""

import argparse
import asyncio
import json
import os
import sys
import time

import yaml

from crawlers.base import RawItem
from crawlers.rss_crawler import RSSCrawler
from crawlers.html_crawler import HTMLCrawler
from crawlers.js_crawler import JSCrawler
from crawlers.api_crawler import ArxivCrawler, ZhihuHotCrawler
from processors.dedup import filter_duplicates, record_seen_items
from processors.boost import apply_boost
from processors.quality import apply_quality
from processors.semantic_dedup import apply_semantic_dedup
from output.writer import write_raw_json, write_clean_markdown
from output.digest import generate_digest
from utils.logger import setup_logger, get_logger
from utils.helpers import generate_run_id, today_path


def write_run_metrics(metrics: dict, settings: dict) -> str:
    """Persist crawl metrics JSON under the configured log dir."""
    log_dir = settings.get("logging", {}).get("dir", "logs")
    os.makedirs(log_dir, exist_ok=True)
    metrics_path = os.path.join(log_dir, f"{metrics['run_id']}_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return metrics_path


def _empty_metrics(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "duration_seconds": 0,
        "sources_total": 0,
        "sources_success": 0,
        "sources_failed": 0,
        "items_total": 0,
        "items_new": 0,
        "items_duplicate": 0,
        "errors": [],
    }


def load_config() -> tuple[list[dict], dict]:
    """Load sources.yaml and settings.yaml."""
    config_dir = os.path.join(os.path.dirname(__file__), "config")

    with open(os.path.join(config_dir, "sources.yaml"), "r", encoding="utf-8") as f:
        sources_config = yaml.safe_load(f)

    with open(os.path.join(config_dir, "settings.yaml"), "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    return sources_config.get("sources", []), settings


def get_crawler(source_config: dict, run_id: str):
    """Factory: return appropriate crawler based on source type."""
    source_type = source_config.get("type", "web")
    js_render = source_config.get("js_render", False)

    if source_type == "rss":
        return RSSCrawler(source_config, run_id)
    elif source_type == "api_arxiv":
        return ArxivCrawler(source_config, run_id)
    elif source_type == "api_zhihu":
        return ZhihuHotCrawler(source_config, run_id)
    elif source_type == "web":
        if js_render:
            return JSCrawler(source_config, run_id)
        return HTMLCrawler(source_config, run_id)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")


async def crawl_all(
    sources: list[dict],
    settings: dict,
    run_id: str,
    source_filter: str | None = None,
    output_date: str | None = None,
    local_only: bool = False,
) -> dict:
    """Main crawl pipeline.

    Per-source failures are recorded in metrics and do not abort the run.
    System-level exceptions propagate after metrics are written when possible.
    """
    logger = get_logger()
    base_dir = settings.get("output", {}).get("base_dir", "data")
    priority_sources = settings.get("digest", {}).get("priority_sources", [])
    start_time = time.time()
    metrics = _empty_metrics(run_id)
    all_items: list[RawItem] = []

    def finalize() -> None:
        metrics["duration_seconds"] = round(time.time() - start_time, 1)
        write_run_metrics(metrics, settings)

    try:
        date_path = today_path(output_date)

        # Filter sources
        active_sources = [s for s in sources if s.get("enabled", True)]
        if source_filter:
            requested_sources = {
                source_id.strip()
                for source_id in source_filter.split(",")
                if source_id.strip()
            }
            active_sources = [s for s in active_sources if s["id"] in requested_sources]
            if not active_sources:
                logger.error(f"Sources '{source_filter}' not found or not enabled")
                metrics["errors"].append(
                    f"Sources '{source_filter}' not found or not enabled"
                )
                finalize()
                return metrics

        metrics["sources_total"] = len(active_sources)

        if local_only:
            logger.info(
                "[mode] local-only: network crawl allowed; "
                "skip Supabase/remote persistence; write only to local data/ and logs/"
            )
        logger.info(f"=== Crawl started ({len(active_sources)} sources) ===")

        for source_config in active_sources:
            try:
                crawler = get_crawler(source_config, run_id)
                items = await crawler.run()
                if items:
                    all_items.extend(items)
                    metrics["sources_success"] += 1
                else:
                    metrics["sources_failed"] += 1
                    metrics["errors"].append(f"{source_config['id']}: no items returned")
            except Exception as e:
                metrics["sources_failed"] += 1
                metrics["errors"].append(f"{source_config['id']}: {str(e)}")
                logger.error(f"[{source_config['id']}] Fatal error: {e}")

        metrics["items_total"] = len(all_items)

        # Dedup
        new_items, dup_count = filter_duplicates(all_items, base_dir)
        logger.info(
            f"[dedup] {len(all_items)} total, {dup_count} duplicates, {len(new_items)} new"
        )

        # Boost scoring
        if new_items:
            new_items = apply_boost(new_items)

        # Quality scoring (rule-based, zero LLM cost)
        quality_threshold = settings.get("quality", {}).get("threshold")
        if new_items:
            new_items = apply_quality(new_items, threshold=quality_threshold)

        # Semantic dedup (TF-IDF title similarity, zero LLM cost)
        sem_threshold = settings.get("dedup", {}).get("semantic_threshold", 0.6)
        if new_items:
            new_items, dup_groups = apply_semantic_dedup(new_items, threshold=sem_threshold)

        # Persist to Supabase only when not in local-only mode.
        # local-only must not import or call storage.db.
        if local_only:
            logger.info("[mode] local-only: Supabase persistence skipped")
        else:
            from storage.db import is_db_available

            if is_db_available() and new_items:
                from storage.signals import SignalRepository

                repo = SignalRepository()
                saved = repo.save_batch(new_items)
                logger.info(f"[db] Persisted {saved} signals to Supabase")

        # Write output
        for item in new_items:
            write_raw_json(item, base_dir, date_path)
            write_clean_markdown(item, base_dir, date_path)

        # Generate digest
        if new_items:
            generate_digest(new_items, base_dir, date_path, run_id, priority_sources)

        # Keep a small ledger outside raw artifacts so fresh CI runners can deduplicate.
        # Record all fetched IDs, including low-quality and semantic duplicates, so they
        # are not reconsidered every day.
        record_seen_items(all_items, base_dir)

        metrics["items_new"] = len(new_items)
        metrics["items_duplicate"] = dup_count
        finalize()
        logger.info(
            f"=== Done: {len(new_items)} new items, "
            f"{metrics['sources_failed']} failed sources, "
            f"{metrics['duration_seconds']}s ==="
        )
        return metrics
    except Exception as exc:
        metrics["items_total"] = len(all_items)
        metrics["errors"].append(f"system: {exc}")
        try:
            finalize()
        except Exception as write_exc:
            logger.error(f"Failed to write metrics after system error: {write_exc}")
        raise


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser (kept compatible with existing flags)."""
    parser = argparse.ArgumentParser(description="ZeroRealm Data Crawler")
    parser.add_argument(
        "--source",
        type=str,
        help="Crawl one source_id or a comma-separated source list",
    )
    parser.add_argument("--date", type=str, help="Specify output date (YYYY-MM-DD)")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help=(
            "Skip Supabase/any remote persistence; write only to local data/ and logs/. "
            "Network crawl of sources is still allowed."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Returns 0 on completed crawl; 1 on system-level failure.

    Individual source failures are recorded in metrics and do not fail this
    process. The collection health gate decides job success from metrics.
    """
    try:
        parser = build_parser()
        args = parser.parse_args(argv)

        run_id = generate_run_id()
        sources, settings = load_config()
        log_level = "DEBUG" if args.debug else settings.get("logging", {}).get("level", "INFO")
        setup_logger(run_id, settings.get("logging", {}).get("dir", "logs"), log_level)

        asyncio.run(
            crawl_all(
                sources,
                settings,
                run_id,
                args.source,
                args.date,
                local_only=args.local_only,
            )
        )
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        try:
            get_logger().exception("System-level crawl failure: %s", exc)
        except Exception:
            print(f"System-level crawl failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
