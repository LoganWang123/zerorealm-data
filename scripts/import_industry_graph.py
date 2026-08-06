"""Compatibility wrapper: import foundation graph nodes into research bootstrap catalog."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    return subprocess.call(
        [sys.executable, str(ROOT / "scripts" / "bootstrap_research_assets.py"), *sys.argv[1:]]
    )


if __name__ == "__main__":
    raise SystemExit(main())
