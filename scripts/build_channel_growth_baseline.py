"""CLI: build privacy-safe channel growth baselines from WeChat xls + Zhihu CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.baseline import build_channel_baseline, write_baseline_artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wechat-xls",
        type=Path,
        required=True,
        help="WeChat tendency BIFF .xls path (read-only input; not copied)",
    )
    parser.add_argument(
        "--zhihu-csv",
        type=Path,
        required=True,
        help="Zhihu daily CSV path (UTF-8; suffix may be .xls)",
    )
    parser.add_argument(
        "--baseline-date",
        default="2026-08-12",
        help="Baseline label date embedded in JSON",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("data/growth/channel-baseline-2026-08-12.json"),
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=Path("docs/reports/channel-growth-baseline-2026-08-13.md"),
    )
    args = parser.parse_args(argv)

    baseline = build_channel_baseline(
        wechat_path=args.wechat_xls,
        zhihu_path=args.zhihu_csv,
        baseline_date=args.baseline_date,
    )
    write_baseline_artifacts(
        baseline,
        json_path=args.json_out,
        markdown_path=args.markdown_out,
    )
    print(f"wrote {args.json_out}")
    print(f"wrote {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
