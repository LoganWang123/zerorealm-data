#!/usr/bin/env python3
"""Generate or verify the hashed website mirror of the canonical registry."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content.canonical_contract import (  # noqa: E402
    MIRROR_PATH,
    build_website_mirror,
    load_json,
    validate_website_mirror,
    write_json,
)


def resolve_website_root(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("ZEROREALM_WEBSITE_ROOT")
    if env:
        return Path(env)
    sibling = ROOT.parent / "zerorealm-website"
    if sibling.is_dir():
        return sibling
    ci = ROOT / ".ci" / "zerorealm-website"
    if ci.is_dir():
        return ci
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed mirrors match regenerated output (no write)",
    )
    parser.add_argument(
        "--website-root",
        type=Path,
        default=None,
        help="zerorealm-website root for writing/checking data/content-canonical.json",
    )
    parser.add_argument(
        "--skip-website",
        action="store_true",
        help="Only sync/check the in-repo website-mirror.json",
    )
    args = parser.parse_args()

    mirror = build_website_mirror()
    report = validate_website_mirror(mirror)
    if not report.ok:
        for issue in report.issues:
            print(issue.format(), file=sys.stderr)
        return 1

    website_root = None if args.skip_website else resolve_website_root(args.website_root)
    website_path = (
        website_root / "data" / "content-canonical.json" if website_root else None
    )

    if args.check:
        ok = True
        if not MIRROR_PATH.is_file():
            print(f"missing {MIRROR_PATH}", file=sys.stderr)
            ok = False
        else:
            committed = load_json(MIRROR_PATH)
            check = validate_website_mirror(committed)
            if not check.ok:
                ok = False
                for issue in check.issues:
                    print(issue.format(), file=sys.stderr)
            if committed.get("mirror", {}).get("source_sha256") != mirror["mirror"][
                "source_sha256"
            ]:
                print("data website-mirror.json is stale", file=sys.stderr)
                ok = False
            if committed.get("families") != mirror.get("families"):
                print("data website-mirror.json families drift", file=sys.stderr)
                ok = False
        if website_path is not None:
            if not website_path.is_file():
                print(f"missing {website_path}", file=sys.stderr)
                ok = False
            else:
                site = load_json(website_path)
                site_check = validate_website_mirror(site)
                if not site_check.ok:
                    ok = False
                    for issue in site_check.issues:
                        print(issue.format(), file=sys.stderr)
                if site.get("mirror", {}).get("source_sha256") != mirror["mirror"][
                    "source_sha256"
                ]:
                    print("website content-canonical.json hash drift", file=sys.stderr)
                    ok = False
                if site.get("families") != mirror.get("families"):
                    print("website content-canonical.json families drift", file=sys.stderr)
                    ok = False
        elif not args.skip_website:
            print(
                "website root not found (set ZEROREALM_WEBSITE_ROOT); "
                "checked data mirror only",
                file=sys.stderr,
            )
        if ok:
            print("canonical mirror check: OK")
            return 0
        print("canonical mirror check: FAIL", file=sys.stderr)
        return 1

    write_json(MIRROR_PATH, mirror)
    print(f"wrote {MIRROR_PATH}")
    if website_path is not None:
        write_json(website_path, mirror)
        print(f"wrote {website_path}")
    elif not args.skip_website:
        print(
            "website root not found; only wrote data mirror "
            "(set ZEROREALM_WEBSITE_ROOT to sync website)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
