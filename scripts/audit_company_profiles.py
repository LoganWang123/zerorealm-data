"""Audit company profiles for human review. Never auto-approves."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.company_audit import audit_company, prioritize_review_queue, rows_as_dicts
from scripts.export_public_bundle import _load_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/research/public-catalog.json"))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--slug")
    parser.add_argument("--only-draft", action="store_true")
    parser.add_argument("--missing-sources", action="store_true")
    parser.add_argument("--missing-summary", action="store_true")
    parser.add_argument("--missing-core-business", action="store_true")
    parser.add_argument("--missing-scenarios", action="store_true")
    parser.add_argument("--stale", action="store_true", help="missing verifiedAt")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--write-review-queue", type=Path, default=None)
    parser.add_argument("--write-review-packages", action="store_true")
    args = parser.parse_args(argv)

    catalog = _load_catalog(args.input)
    rows = [audit_company(company) for company in catalog.companies.values()]

    if args.slug:
        rows = [row for row in rows if row.slug == args.slug]
    elif not args.all:
        rows = [row for row in rows if row.status == "draft"]

    if args.only_draft:
        rows = [row for row in rows if row.status == "draft"]
    if args.missing_sources:
        rows = [row for row in rows if row.source_count == 0]
    if args.missing_summary:
        rows = [row for row in rows if "summary" in row.missing_fields]
    if args.missing_core_business:
        rows = [row for row in rows if "coreBusiness" in row.missing_fields]
    if args.missing_scenarios:
        rows = [row for row in rows if "scenarios" in row.missing_fields]
    if args.stale:
        rows = [row for row in rows if "verifiedAt" in row.missing_fields]

    payload = rows_as_dicts(rows)
    if args.format == "json":
        print(json.dumps({"count": len(payload), "companies": payload}, ensure_ascii=False, indent=2))
    else:
        lines = ["# Company Audit", ""]
        for row in payload:
            lines.append(f"## {row['name']} (`{row['slug']}`)")
            lines.append(f"- status: {row['status']}")
            lines.append(f"- readiness: {row['readiness']}")
            lines.append(f"- missing: {', '.join(row['missing_fields']) or '—'}")
            lines.append(f"- risks: {'; '.join(row['risks']) or '—'}")
            lines.append("")
        print("\n".join(lines))

    if args.write_review_queue:
        queue_source = [audit_company(c) for c in catalog.companies.values() if c.status == "draft"]
        queue = prioritize_review_queue(queue_source, limit=10)
        args.write_review_queue.parent.mkdir(parents=True, exist_ok=True)
        args.write_review_queue.write_text(
            json.dumps(
                {
                    "generatedFor": "human-review-only",
                    "autoApproved": False,
                    "items": rows_as_dicts(queue),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.write_review_packages:
        out_root = Path("dist/review/company")
        for row in rows:
            package_dir = out_root / row.slug
            package_dir.mkdir(parents=True, exist_ok=True)
            risk_lines = [f"- {risk}" for risk in row.risks] or ["- —"]
            md = "\n".join(
                [
                    f"# 企业审核包：{row.name}",
                    "",
                    f"- slug: `{row.slug}`",
                    f"- status: `{row.status}`（不得自动批准）",
                    f"- readiness: `{row.readiness}`",
                    f"- coreBusiness: {row.core_business or '—'}",
                    f"- verifiedAt: {row.verified_at or '—'}",
                    f"- missing: {', '.join(row.missing_fields) or '—'}",
                    "",
                    "## Summary",
                    row.summary or "（空）",
                    "",
                    "## Risks",
                    *risk_lines,
                    "",
                    "## Relations",
                    "```json",
                    json.dumps(row.relations, ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "> 内部字段不应出现在 Public Bundle。本审核包仅供人工使用。",
                    "",
                ]
            )
            (package_dir / "review.md").write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
