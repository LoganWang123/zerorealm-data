#!/usr/bin/env python3
"""Validate cross-channel canonical content contract (SSoT + packets + mirror)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content.canonical_contract import check_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--website-root",
        type=Path,
        default=None,
        help="Path to zerorealm-website (default: sibling, .ci/, or ZEROREALM_WEBSITE_ROOT)",
    )
    parser.add_argument(
        "--require-website",
        action="store_true",
        help="Fail if website root cannot be resolved",
    )
    args = parser.parse_args()
    website = args.website_root
    if website is None:
        env = os.environ.get("ZEROREALM_WEBSITE_ROOT")
        if env:
            website = Path(env)

    report = check_all(
        root=ROOT,
        website_root=website,
        require_website=args.require_website,
    )
    if report.ok:
        print("canonical contract check: OK")
        return 0
    for issue in report.issues:
        print(issue.format(), file=sys.stderr)
    print(f"canonical contract check: FAIL ({len(report.issues)} issues)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
