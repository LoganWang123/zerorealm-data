"""Generate daily report from crawled data using LLM.

Usage:
    python generate_daily.py                  # 生成今日日报
    python generate_daily.py --date 2026-07-26
    python generate_daily.py --issue 1

Environment:
    LLM_API_KEY      - API key (required)
    LLM_BASE_URL     - API base URL (default: https://api.openai.com/v1)
    LLM_MODEL        - Model name (default: gpt-4o-mini)
"""

import argparse
import os
import sys

from utils.logger import setup_logger, get_logger
from utils.helpers import generate_run_id


def main():
    parser = argparse.ArgumentParser(description="ZeroRealm Daily Report Generator")
    parser.add_argument("--date", type=str, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--issue", type=int, help="Issue number (auto if omitted)")
    parser.add_argument("--output", type=str, default="output_daily", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("LLM_API_KEY"):
        print("Error: LLM_API_KEY environment variable is required.")
        print("  set LLM_API_KEY=your-api-key")
        print("  set LLM_BASE_URL=https://api.openai.com/v1  (optional)")
        print("  set LLM_MODEL=gpt-4o-mini  (optional)")
        sys.exit(1)

    # Init logger
    run_id = generate_run_id()
    level = "DEBUG" if args.debug else "INFO"
    setup_logger(run_id, "logs", level)
    logger = get_logger()

    logger.info("=== Daily Report Generator ===")

    from generators.daily_report import generate_daily_report

    result = generate_daily_report(
        base_dir="data",
        output_dir=args.output,
        date=args.date,
        issue=args.issue,
    )

    if result:
        logger.info(f"=== Done: {result} ===")
    else:
        logger.warning("=== No report generated (no data or LLM error) ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
