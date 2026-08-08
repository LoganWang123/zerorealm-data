"""Patch Daily MDX frontmatter without rewriting body semantics."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from publishing.website.mdx_adapter import extract_frontmatter


def patch_frontmatter(path: Path, updates: dict) -> None:
    text = path.read_text(encoding="utf-8")
    data, body = extract_frontmatter(text)
    data.update({k: v for k, v in updates.items() if v is not None})
    dumped = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip() + "\n"
    if body.strip():
        path.write_text(f"---\n{dumped}---\n{body}", encoding="utf-8")
    else:
        path.write_text(f"---\n{dumped}---\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args()
    updates: dict = {}
    for item in args.set:
        key, _, value = item.partition("=")
        updates[key] = value
    patch_frontmatter(args.path, updates)
    print(f"patched {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
