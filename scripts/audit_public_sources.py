"""Audit public sources in the research catalog.

Does not pretend network validation succeeded when offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_public_bundle import _load_catalog


def audit_sources(catalog_path: Path, *, check_network: bool = False) -> dict:
    catalog = _load_catalog(catalog_path)
    issues = []
    by_url: dict[str, list[str]] = defaultdict(list)
    for source in catalog.sources.values():
        if not source.url:
            issues.append({"code": "MISSING_URL", "id": source.id, "severity": "error"})
        else:
            parsed = urlparse(source.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                issues.append({"code": "INVALID_URL", "id": source.id, "severity": "error"})
            by_url[source.url.rstrip("/").lower()].append(source.id)
        if not source.source_name and not getattr(source, "publisher", ""):
            issues.append({"code": "MISSING_PUBLISHER", "id": source.id, "severity": "warning"})
        if not source.published_at:
            issues.append({"code": "MISSING_PUBLISHED_AT", "id": source.id, "severity": "info"})
        if not source.credibility:
            issues.append({"code": "MISSING_CREDIBILITY", "id": source.id, "severity": "warning"})
        if not source.source_type:
            issues.append({"code": "MISSING_SOURCE_TYPE", "id": source.id, "severity": "warning"})

    for url, ids in by_url.items():
        if len(ids) > 1:
            issues.append(
                {
                    "code": "CANONICAL_DUPLICATE",
                    "url": url,
                    "ids": ids,
                    "severity": "warning",
                }
            )

    network = {"status": "network_not_checked", "checked": 0}
    if check_network:
        try:
            import requests  # noqa: WPS433
        except ImportError:
            network = {"status": "network_not_checked", "reason": "requests_missing"}
        else:
            network = {"status": "checked", "checked": 0, "failures": []}
            for source in list(catalog.sources.values())[:20]:
                if not source.url:
                    continue
                try:
                    response = requests.head(source.url, timeout=5, allow_redirects=True)
                    network["checked"] += 1
                    if response.status_code >= 400:
                        network["failures"].append(
                            {"id": source.id, "status": response.status_code}
                        )
                except requests.RequestException:
                    network["failures"].append({"id": source.id, "status": "error"})
                    network["checked"] += 1

    return {
        "sourceCount": len(catalog.sources),
        "issueCount": len(issues),
        "issues": issues,
        "network": network,
        "note": "network_not_checked means URLs were not live-verified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/research/public-catalog.json"))
    parser.add_argument("--check-network", action="store_true")
    args = parser.parse_args()
    report = audit_sources(args.input, check_network=args.check_network)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["issueCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
