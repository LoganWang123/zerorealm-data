"""Export industry-map dataset from research catalog.

Default: approved/published only.
--include-draft marks output FOR_REVIEW_ONLY and must not be treated as public.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_public_bundle import _load_catalog
from research.serialization import serialize_case, serialize_company


def export_dataset(catalog_path: Path, out: Path, *, include_draft: bool) -> dict:
    catalog = _load_catalog(catalog_path)
    companies = []
    for company in catalog.companies.values():
        if company.status in {"approved", "published"} or (
            include_draft and company.status == "draft"
        ):
            companies.append(serialize_company(company))
    cases = []
    for case in catalog.cases.values():
        if case.status in {"approved", "published"} or (
            include_draft and case.status == "draft"
        ):
            cases.append(serialize_case(case))
    payload = {
        "visibility": "FOR_REVIEW_ONLY" if include_draft else "PUBLIC_CANDIDATE",
        "includeDraft": include_draft,
        "companies": companies,
        "cases": cases,
        "autoApproved": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(out),
        "companyCount": len(companies),
        "caseCount": len(cases),
        "visibility": payload["visibility"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/research/public-catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("dist/industry-map-dataset.json"))
    parser.add_argument("--include-draft", action="store_true")
    args = parser.parse_args()
    report = export_dataset(args.input, args.output, include_draft=args.include_draft)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
