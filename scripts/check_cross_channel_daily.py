"""CLI: fail when WeChat Daily success lacks website artifact."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publishing.cross_channel import find_cross_channel_issues, format_issues
from publishing.manifest_repository import ManifestRepository


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-daily-dir",
        type=Path,
        default=Path("output_daily"),
    )
    parser.add_argument(
        "--website-daily-dir",
        type=Path,
        default=Path("../zerorealm-website/content/daily"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("storage/manifest/manifest.json"),
    )
    parser.add_argument(
        "--now",
        help="Override now ISO datetime (Asia/Shanghai assumed if naive)",
    )
    args = parser.parse_args()

    now = None
    if args.now:
        now = datetime.fromisoformat(args.now)

    issues = find_cross_channel_issues(
        output_daily_dir=args.output_daily_dir,
        website_daily_dir=args.website_daily_dir,
        manifest=ManifestRepository(args.manifest),
        now=now,
    )
    if issues:
        print(format_issues(issues), file=sys.stderr)
        return 1
    print("cross-channel daily check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
