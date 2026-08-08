"""Extract source URL candidates from existing daily MDX into draft research notes.

Does not auto-approve claims. Output is a review checklist JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SOURCE_RE = re.compile(r"https?://[^\s\)\"']+")


def migrate(mdx_dir: Path) -> dict:
    candidates = []
    for path in sorted(mdx_dir.glob("*.mdx")):
        text = path.read_text(encoding="utf-8")
        urls = sorted(set(SOURCE_RE.findall(text)))
        if not urls:
            continue
        candidates.append(
            {
                "article": path.name,
                "status": "reviewing",
                "sourceUrls": urls,
                "note": "Needs human claim extraction; do not publish automatically.",
            }
        )
    return {
        "generatedFrom": str(mdx_dir),
        "candidateCount": len(candidates),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mdx-dir",
        type=Path,
        default=Path("output_daily"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/research/article-migration-candidates.json"),
    )
    args = parser.parse_args()
    payload = migrate(args.mdx_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"candidateCount": payload["candidateCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
