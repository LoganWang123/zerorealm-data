"""Audit a research catalog for missing URLs and unpublished facts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_public_bundle import _load_catalog
from research.models import ClaimStatus, ClaimType


def audit(catalog_path: Path) -> dict:
    catalog = _load_catalog(catalog_path)
    issues = []
    for claim in catalog.claims.values():
        if claim.type is ClaimType.FACT and claim.status is ClaimStatus.VERIFIED:
            if not claim.source_ids:
                issues.append({"code": "FACT_MISSING_SOURCE", "id": claim.id})
            for source_id in claim.source_ids:
                source = catalog.sources.get(source_id)
                if source is None or not source.url:
                    issues.append(
                        {"code": "SOURCE_MISSING_URL", "id": claim.id, "sourceId": source_id}
                    )
    draft_companies = [
        company.id for company in catalog.companies.values() if company.status == "draft"
    ]
    return {
        "issueCount": len(issues),
        "issues": issues,
        "draftCompanyCount": len(draft_companies),
        "approvedMetricCount": sum(
            1 for metric in catalog.metrics.values() if metric.status == "approved"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/research/public-catalog.json"),
    )
    args = parser.parse_args()
    report = audit(args.input)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["issueCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
