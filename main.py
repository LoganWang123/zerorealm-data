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
from processors.dedup import filter_duplicates
from processors.boost import apply_boost
from output.writer import write_raw_json, write_clean_markdown
from output.digest import generate_digest
from utils.logger import setup_logger, get_logger
from utils.helpers import generate_run_id, today_path


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

    if source_type == "rss":
        return RSSCrawler(source_config, run_id)
    elif source_type == "web":
        return HTMLCrawler(source_config, run_id)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")


async def crawl_all(sources: list[dict], settings: dict, run_id: str, source_filter: str | None = None):
    """Main crawl pipeline."""
    logger = get_logger()
    base_dir = settings.get("output", {}).get("base_dir", "data")
    priority_sources = settings.get("digest", {}).get("priority_sources", [])
    date_path = today_path()

    # Filter sources
    active_sources = [s for s in sources if s.get("enabled", True)]
    if source_filter:
        active_sources = [s for s in active_sources if s["id"] == source_filter]
        if not active_sources:
            logger.error(f"Source '{source_filter}' not found or not enabled")
            return

    logger.info(f"=== Crawl started ({len(active_sources)} sources) ===")
    start_time = time.time()

    all_items: list[RawItem] = []
    sources_success = 0
    sources_failed = 0
    errors = []

    for source_config in active_sources:
        try:
            crawler = get_crawler(source_config, run_id)
            items = await crawler.run()
            if items:
                all_items.extend(items)
                sources_success += 1
            else:
                sources_failed += 1
                errors.append(f"{source_config['id']}: no items returned")
        except Exception as e:
            sources_failed += 1
            errors.append(f"{source_config['id']}: {str(e)}")
            logger.error(f"[{source_config['id']}] Fatal error: {e}")

    # Dedup
    new_items, dup_count = filter_duplicates(all_items, base_dir)
    logger.info(f"[dedup] {len(all_items)} total, {dup_count} duplicates, {len(new_items)} new")

    # Boost scoring
    if new_items:
        new_items = apply_boost(new_items)

    # Write output
    for item in new_items:
        write_raw_json(item, base_dir, date_path)
        write_clean_markdown(item, base_dir, date_path)

    # Generate digest
    if new_items:
        generate_digest(new_items, base_dir, date_path, run_id, priority_sources)

    # Metrics
    duration = round(time.time() - start_time, 1)
    metrics = {
        "run_id": run_id,
        "duration_seconds": duration,
        "sources_total": len(active_sources),
        "sources_success": sources_success,
        "sources_failed": sources_failed,
        "items_total": len(all_items),
        "items_new": len(new_items),
        "items_duplicate": dup_count,
        "errors": errors,
    }

    # Write metrics
    log_dir = settings.get("logging", {}).get("dir", "logs")
    os.makedirs(log_dir, exist_ok=True)
    metrics_path = os.path.join(log_dir, f"{run_id}_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    logger.info(
        f"=== Done: {len(new_items)} new items, "
        f"{sources_failed} failed sources, {duration}s ==="
    )


def main():
    parser = argparse.ArgumentParser(description="ZeroRealm Data Crawler")
    parser.add_argument("--source", type=str, help="Only crawl specified source_id")
    parser.add_argument("--date", type=str, help="Specify output date (YYYY-MM-DD)")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args()

    # Init
    run_id = generate_run_id()
    sources, settings = load_config()
    log_level = "DEBUG" if args.debug else settings.get("logging", {}).get("level", "INFO")
    setup_logger(run_id, settings.get("logging", {}).get("dir", "logs"), log_level)

    # Run
    asyncio.run(crawl_all(sources, settings, run_id, args.source))


if __name__ == "__main__":
    main()
