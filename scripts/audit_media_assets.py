"""Audit local media assets. Never deletes files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from publishing.media_generation.asset_checks import inspect_image_file


def audit(roots: list[Path]) -> dict:
    buckets = {
        "missing": [],
        "pending": [],
        "approved": [],
        "rejected": [],
        "wrong_ratio": [],
        "oversized": [],
        "corrupt": [],
        "missing_alt": [],
        "missing_source": [],
        "agnes_legacy": [],
    }
    for root in roots:
        if not root.exists():
            buckets["missing"].append(str(root))
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            lower = str(path).lower()
            if "agnes" in lower:
                buckets["agnes_legacy"].append(str(path))
            report = inspect_image_file(path)
            if report["corrupted"]:
                buckets["corrupt"].append(str(path))
            if report["sizeBytes"] and report["sizeBytes"] > 8_000_000:
                buckets["oversized"].append(str(path))
            if "approved" in lower:
                buckets["approved"].append(str(path))
            elif "pending" in lower or "generated" in lower:
                buckets["pending"].append(str(path))
            if "rejected" in lower:
                buckets["rejected"].append(str(path))
    return {key: {"count": len(value), "paths": value[:50]} for key, value in buckets.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    roots = args.root or [
        Path("assets/generated"),
        Path("output/media"),
        Path("assets/covers"),
    ]
    print(json.dumps(audit(roots), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
