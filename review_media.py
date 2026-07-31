"""Record an explicit visual approval for generated daily media."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from publishing.media_generation.review import approve_media_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Approve visually reviewed media using exact SHA-256 hashes"
    )
    parser.add_argument("--date", required=True, help="Report date (YYYY-MM-DD)")
    parser.add_argument(
        "--approve",
        action="append",
        default=[],
        metavar="ROLE=SHA256",
        help="Exact reviewed asset hash; repeat once for every asset",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    approvals: dict[str, str] = {}
    for value in args.approve:
        if "=" not in value:
            print(f"Invalid approval: {value}", file=sys.stderr)
            return 2
        role, digest = value.split("=", 1)
        if not role or len(digest) != 64:
            print(f"Invalid approval: {value}", file=sys.stderr)
            return 2
        approvals[role] = digest
    manifest_path = Path("assets") / "generated" / args.date / "media-manifest.json"
    try:
        approve_media_manifest(manifest_path, approvals)
    except ValueError as exc:
        print(f"Media review failed: {exc}", file=sys.stderr)
        return 1
    print(f"Approved reviewed media: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
