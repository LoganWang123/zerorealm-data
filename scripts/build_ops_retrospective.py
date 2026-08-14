"""CLI: local channel-report import + freshness-gated operating retrospective.

Reads WeChat/Zhihu exports in place (does not copy raw reports or PII).
Stale reports never fill current_experiment channel counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.report_discovery import (  # noqa: E402
    discover_wechat_tendency,
    discover_zhihu_daily,
    parse_wechat_or_raise,
)
from growth.retrospective import (  # noqa: E402
    build_ops_retrospective,
    write_ops_retrospective_artifacts,
)
from growth.zhihu import parse_zhihu_daily_csv  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-date", default="2026-08-15")
    parser.add_argument("--generated-on", default=None)
    parser.add_argument("--import-dir", type=Path, default=None)
    parser.add_argument("--wechat-xls", type=Path, default=None)
    parser.add_argument("--zhihu-csv", type=Path, default=None)
    parser.add_argument(
        "--baseline-json",
        type=Path,
        default=Path("data/growth/channel-baseline-2026-08-12.json"),
    )
    parser.add_argument(
        "--collection-snapshot-json",
        type=Path,
        default=None,
        help="Technical collection run snapshot (not business metrics)",
    )
    parser.add_argument("--experiment-start", default="2026-08-13")
    parser.add_argument("--experiment-end", default="2026-08-26")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("data/growth/ops-retrospective-2026-08-15.json"),
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=Path("docs/reports/ops-retrospective-2026-08-15.md"),
    )
    args = parser.parse_args(argv)

    if not args.baseline_json.is_file():
        print(f"baseline not found: {args.baseline_json}", file=sys.stderr)
        return 1

    wechat_filename = ""
    zhihu_filename = ""
    zhihu_aliases: tuple[str, ...] = ()
    wechat_reason = ""
    zhihu_reason = ""

    if args.wechat_xls is not None:
        wechat_path = args.wechat_xls
        wechat_filename = wechat_path.name
        wechat_reason = "explicit --wechat-xls"
    elif args.import_dir is not None:
        discovered = discover_wechat_tendency(args.import_dir)
        wechat_path = discovered.path
        wechat_filename = discovered.filename
        wechat_reason = discovered.selection_reason
    else:
        print("need --wechat-xls or --import-dir", file=sys.stderr)
        return 1

    if args.zhihu_csv is not None:
        zhihu_path = args.zhihu_csv
        zhihu_filename = zhihu_path.name
        zhihu_reason = "explicit --zhihu-csv"
    elif args.import_dir is not None:
        discovered_z = discover_zhihu_daily(args.import_dir)
        zhihu_path = discovered_z.path
        zhihu_filename = discovered_z.filename
        zhihu_aliases = discovered_z.aliases
        zhihu_reason = discovered_z.selection_reason
    else:
        print("need --zhihu-csv or --import-dir", file=sys.stderr)
        return 1

    wechat = parse_wechat_or_raise(wechat_path)
    zhihu = parse_zhihu_daily_csv(zhihu_path)
    baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
    collection = None
    if args.collection_snapshot_json is not None:
        if not args.collection_snapshot_json.is_file():
            print(
                f"collection snapshot not found: {args.collection_snapshot_json}",
                file=sys.stderr,
            )
            return 1
        collection = json.loads(args.collection_snapshot_json.read_text(encoding="utf-8"))

    payload = build_ops_retrospective(
        review_date=args.review_date,
        baseline=baseline,
        wechat=wechat,
        zhihu=zhihu,
        wechat_filename=wechat_filename,
        zhihu_filename=zhihu_filename,
        zhihu_aliases=zhihu_aliases,
        wechat_selection_reason=wechat_reason,
        zhihu_selection_reason=zhihu_reason,
        collection=collection,
        experiment_start=args.experiment_start,
        experiment_end=args.experiment_end,
        generated_on=args.generated_on or args.review_date,
    )
    write_ops_retrospective_artifacts(
        payload, json_path=args.json_out, markdown_path=args.markdown_out
    )
    print(f"wrote {args.json_out}")
    print(f"wrote {args.markdown_out}")
    nxt = payload["next_work_item"]
    print(f"next_work_item={nxt['id']} review={nxt['next_review_date']}")
    print(
        "current_experiment_import.applied="
        f"{payload['business_channels']['current_experiment_import']['applied']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
