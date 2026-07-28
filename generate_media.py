"""Manual media generation commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from publishing.media_generation.homepage import (
    client_from_environment,
    generate_homepage_media,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ZeroRealm media with Agnes")
    subparsers = parser.add_subparsers(dest="command", required=True)
    homepage = subparsers.add_parser("homepage", help="Generate fixed homepage media")
    homepage.add_argument(
        "--website-root",
        default="../zerorealm-website",
        help="Path to the zerorealm-website repository",
    )
    homepage.add_argument(
        "--force",
        action="store_true",
        help="Replace existing homepage media after a successful generation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(__file__).parent / ".env")
    args = build_parser().parse_args(argv)
    try:
        manifest = generate_homepage_media(
            client=client_from_environment(),
            website_root=args.website_root,
            force=args.force,
        )
    except Exception as exc:
        print(f"Media generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Homepage media manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
