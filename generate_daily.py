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

from dotenv import load_dotenv

from utils.logger import setup_logger, get_logger
from utils.helpers import generate_run_id
from utils.github_actions_safety import GENERATION_SKIP_REASON, is_github_actions


def main():
    # Runtime kill switch for the transitional GitHub workflow. Keep this
    # before dotenv loading and credential checks so Actions can never invoke
    # a project-managed LLM, even when the legacy step injects an API key.
    if is_github_actions():
        print(GENERATION_SKIP_REASON)
        return 2

    load_dotenv()
    parser = argparse.ArgumentParser(description="ZeroRealm Daily Report Generator")
    parser.add_argument("--date", type=str, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--issue", type=int, help="Issue number (auto if omitted)")
    parser.add_argument("--output", type=str, default="output_daily", help="Output directory")
    parser.add_argument(
        "--history-dir",
        type=str,
        help="Published MDX directory used for issue numbering and duplicate checks",
    )
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("LLM_API_KEY"):
        print("Error: LLM_API_KEY environment variable is required.")
        print("  set LLM_API_KEY=your-api-key")
        print("  set LLM_BASE_URL=https://api.openai.com/v1  (optional)")
        print("  set LLM_MODEL=gpt-4o-mini  (optional)")
        return 1

    # Init logger
    run_id = generate_run_id()
    level = "DEBUG" if args.debug else "INFO"
    setup_logger(run_id, "logs", level)
    logger = get_logger()

    logger.info("=== Daily Report Generator ===")

    from generators.daily_report import DuplicateDailyReportError, generate_daily_report

    try:
        result = generate_daily_report(
            base_dir="data",
            output_dir=args.output,
            date=args.date,
            issue=args.issue,
            history_dir=args.history_dir,
        )
    except DuplicateDailyReportError as exc:
        logger.warning(f"=== Duplicate report skipped: {exc} ===")
        return 2

    if result:
        logger.info(f"=== Done: {result} ===")
    else:
        logger.warning("=== No report generated (no data or LLM error) ===")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
