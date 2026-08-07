"""Export industry-map dataset files for V1 prep (review-only when drafts included)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.relations import build_relation_index
from research.serialization import serialize_case, serialize_company
from scripts.export_public_bundle import _load_catalog


CATEGORIES = [
    {"id": "operator", "name": "运营平台"},
    {"id": "hardware", "name": "设备/硬件"},
    {"id": "software", "name": "软件/AI"},
    {"id": "brand", "name": "品牌"},
    {"id": "scenario", "name": "场景"},
]


def export_dataset(catalog_path: Path, out_dir: Path, *, include_draft: bool) -> dict:
    catalog = _load_catalog(catalog_path)
    companies = []
    missing_sources = []
    review_status = []
    for company in catalog.companies.values():
        allowed = company.status in {"approved", "published"} or (
            include_draft and company.status == "draft"
        )
        if not allowed:
            continue
        companies.append(serialize_company(company))
        review_status.append(
            {
                "id": company.id,
                "slug": company.slug,
                "status": company.status,
                "verifiedAt": company.verified_at,
                "provenance": "research_catalog",
            }
        )
        if not company.verified_at:
            missing_sources.append(
                {"id": company.id, "slug": company.slug, "reason": "missing_verifiedAt"}
            )

    cases = []
    for case in catalog.cases.values():
        if case.status in {"approved", "published"} or (
            include_draft and case.status == "draft"
        ):
            cases.append(serialize_case(case))

    relations = build_relation_index(catalog)
    visibility = "FOR_REVIEW_ONLY" if include_draft else "PUBLIC_CANDIDATE"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "companies.json": {
            "visibility": visibility,
            "includeDraft": include_draft,
            "companies": companies,
            "cases": cases,
        },
        "categories.json": {"categories": CATEGORIES},
        "relations.json": relations,
        "missing-sources.json": {"items": missing_sources},
        "review-status.json": {
            "visibility": visibility,
            "autoApproved": False,
            "items": review_status,
        },
    }
    for name, payload in files.items():
        (out_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return {
        "outDir": str(out_dir),
        "companyCount": len(companies),
        "caseCount": len(cases),
        "visibility": visibility,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/research/public-catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("dist/industry-map-v1"))
    parser.add_argument("--include-draft", action="store_true")
    args = parser.parse_args()
    report = export_dataset(args.input, args.output, include_draft=args.include_draft)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
