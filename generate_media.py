"""Manual media commands.

Agnes homepage generation is disabled. Prefer:
  python scripts/generate_local_media.py <content-id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from publishing.media_generation.errors import AgnesImageGenerationDisabled


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deprecated Agnes entrypoint — use scripts/generate_local_media.py"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    homepage = subparsers.add_parser(
        "homepage",
        help="DEPRECATED: Agnes homepage generation is disabled",
    )
    homepage.add_argument("--website-root", default="../zerorealm-website")
    homepage.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(__file__).parent / ".env")
    build_parser().parse_args(argv)
    print(
        "AGNES_IMAGE_GENERATION_DISABLED: use python scripts/generate_local_media.py",
        file=sys.stderr,
    )
    raise AgnesImageGenerationDisabled(
        "generate_media.py homepage path is disabled; use scripts/generate_local_media.py"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AgnesImageGenerationDisabled as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
