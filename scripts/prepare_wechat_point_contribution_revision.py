#!/usr/bin/env python3
"""Prepare WeChat point-contribution production revision artifacts (no OA mutation)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.wechat_point_contribution_revision import (  # noqa: E402
    build_revision_packet,
    write_revision_artifacts,
)


def main() -> int:
    paths = write_revision_artifacts(ROOT)
    packet = build_revision_packet()
    print(
        json.dumps(
            {
                "status": packet["status"],
                "external_sync_status": packet["external_sync_status"],
                "paths": {k: str(v.relative_to(ROOT)) for k, v in paths.items()},
                "external_draft": packet["external_draft"],
                "cta": packet["cta"]["copy"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
