"""CLI: generate founder growth scorecard, funnel rates, and weekly decisions.

Reads an existing privacy-safe baseline JSON (does not copy raw WeChat/Zhihu
reports or PII). Optionally accepts a filled experiment ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.ledger import (  # noqa: E402
    load_ledger,
    write_ledger_schema,
    write_ledger_template,
)
from growth.ops import (  # noqa: E402
    generate_founder_growth_ops,
    write_founder_growth_ops_artifacts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-json",
        type=Path,
        default=Path("data/growth/channel-baseline-2026-08-12.json"),
        help="Privacy-safe baseline JSON (aggregates only)",
    )
    parser.add_argument(
        "--ledger-json",
        type=Path,
        default=None,
        help=(
            "Optional filled current-period experiment ledger; "
            "default creates empty current-period ledger "
            "(targets from baseline only; channel counts stay null)"
        ),
    )
    parser.add_argument(
        "--start-date",
        default="2026-08-13",
        help="Combat pack start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/growth/ops-out"),
        help="Directory for generated JSON/Markdown artifacts",
    )
    parser.add_argument(
        "--write-templates",
        action="store_true",
        help="Also write experiment-ledger.schema.json and .template.json",
    )
    parser.add_argument(
        "--slots-per-week",
        type=int,
        default=4,
        help="Empty target account slots per week (3–5)",
    )
    args = parser.parse_args(argv)

    if not args.baseline_json.is_file():
        print(f"baseline not found: {args.baseline_json}", file=sys.stderr)
        return 1

    baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
    ledger = load_ledger(args.ledger_json) if args.ledger_json else None

    if args.write_templates:
        schema_path = Path("data/growth/experiment-ledger.schema.json")
        template_path = Path("data/growth/experiment-ledger.template.json")
        write_ledger_schema(schema_path)
        write_ledger_template(template_path)
        print(f"wrote {schema_path}")
        print(f"wrote {template_path}")

    bundle = generate_founder_growth_ops(
        baseline=baseline,
        ledger=ledger,
        start_date=args.start_date,
        slots_per_week=args.slots_per_week,
    )
    paths = write_founder_growth_ops_artifacts(bundle, out_dir=args.out_dir)
    for key, path in paths.items():
        print(f"wrote {key}: {path}")

    # Convenience copies into docs/reports for the default campaign.
    reports = Path("docs/reports")
    reports.mkdir(parents=True, exist_ok=True)
    combat_report = reports / "founder-growth-combat-pack-2026-08-13.md"
    scorecard_report = reports / "founder-growth-scorecard-2026-08-13.md"
    decisions_report = reports / "founder-growth-weekly-decisions-2026-08-13.md"
    combat_report.write_text(paths["combat_md"].read_text(encoding="utf-8"), encoding="utf-8")
    scorecard_report.write_text(
        paths["scorecard_md"].read_text(encoding="utf-8"), encoding="utf-8"
    )
    decisions_report.write_text(
        paths["decisions_md"].read_text(encoding="utf-8"), encoding="utf-8"
    )
    outreach_ops = Path("docs/operations/founder-growth-outreach-templates.md")
    outreach_ops.parent.mkdir(parents=True, exist_ok=True)
    outreach_ops.write_text(paths["outreach_md"].read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {combat_report}")
    print(f"wrote {scorecard_report}")
    print(f"wrote {decisions_report}")
    print(f"wrote {outreach_ops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
