#!/usr/bin/env python3
"""Read-only WeChat draft inspection for content ops phase 1.

Safety:
- Loads WECHAT_APPID / WECHAT_SECRET only (never prints them).
- Calls draft/batchget list only.
- Never calls delete_draft, update_draft, create_draft, submit_publish, or mass-send.
- Does not load or call project LLM APIs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.content_ops_phase1 import inspect_draft_payload  # noqa: E402
from publishing.wechat.client import WechatAPIError, WechatClient  # noqa: E402

DEFAULT_SECRET_CANDIDATES = [
    ROOT / ".env",
    Path(
        "/Users/Logan/AICoding/ZeroRealmAI/ZeroRealmAI-migrate-manual-20260812/"
        "secrets/zerorealm-data.env"
    ),
]


def _load_wechat_env(env_path: Path | None) -> tuple[str, str]:
    app_id = os.environ.get("WECHAT_APPID", "").strip()
    secret = os.environ.get("WECHAT_SECRET", "").strip()
    if app_id and secret:
        return app_id, secret

    candidates = [env_path] if env_path else DEFAULT_SECRET_CANDIDATES
    for path in candidates:
        if path is None or not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "WECHAT_APPID" and value and "your-appid" not in value.lower():
                app_id = value
            elif key == "WECHAT_SECRET" and value and "your-secret" not in value.lower():
                secret = value
        if app_id and secret:
            # Do not export LLM keys even if present in the same file.
            return app_id, secret
    raise SystemExit(
        "WECHAT_APPID/WECHAT_SECRET not found in environment or known secret files."
    )


def _paginate_drafts(client: WechatClient, *, page_size: int = 20) -> dict:
    all_items: list[dict] = []
    offset = 0
    total = None
    while True:
        payload = client.list_drafts(offset=offset, count=page_size, no_content=0)
        if total is None:
            total = int(payload.get("total_count") or 0)
        items = payload.get("item") or []
        all_items.extend(items)
        if not items:
            break
        offset += len(items)
        if total is not None and offset >= total:
            break
        if len(items) < page_size:
            break
    return {
        "total_count": total if total is not None else len(all_items),
        "item_count": len(all_items),
        "item": all_items,
    }


def render_markdown_report(report: dict) -> str:
    lines = [
        "# WeChat draft inspection · 2026-08-15",
        "",
        f"- Inspected at: `{report.get('inspected_at')}`",
        f"- Mode: **{report.get('mode')}** (list only)",
        f"- total_count: **{report.get('total_count')}**",
        f"- item_count: **{report.get('item_count')}**",
        "",
        "## Safety",
        "",
        "- delete / overwrite / publish / mass-send: **not performed**",
        "- LLM API: **not called**",
        "- image generation: **not performed**",
        "",
        "## Drafts (title / update / media status)",
        "",
    ]
    drafts = report.get("drafts") or []
    if not drafts:
        lines.append("_No unpublished drafts returned._")
    else:
        lines.extend(
            [
                "| # | media_id (prefix) | update_time | titles | thumb |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for idx, draft in enumerate(drafts, start=1):
            mid = str(draft.get("media_id") or "")
            prefix = (mid[:10] + "…") if len(mid) > 10 else mid
            titles = " / ".join(draft.get("titles") or []) or "(untitled)"
            thumb = "yes" if draft.get("media_status", {}).get("any_thumb_present") else "no"
            lines.append(
                f"| {idx} | `{prefix}` | {draft.get('update_time')} | {titles} | {thumb} |"
            )

    lines.extend(["", "## Overlap with approved plan", ""])
    overlaps = report.get("plan_overlap") or []
    if not overlaps:
        lines.append("_No title keyword overlap with phase-1 plan pieces._")
    else:
        for hit in overlaps:
            lines.append(
                f"- `media_id` prefix `{str(hit.get('media_id', ''))[:10]}…` → "
                f"**{hit.get('piece_id')}** (hints: {', '.join(hit.get('matched_hints') or [])})"
            )
            for title in hit.get("titles") or []:
                lines.append(f"  - {title}")

    lines.extend(
        [
            "",
            "## Policy",
            "",
            str(report.get("unknown_draft_policy") or ""),
            "",
            "## Exception check (CEO plan)",
            "",
            "If an unpublished draft overlaps `w1-wechat-five-metrics`, "
            "prioritize human WeChat publish on 2026-08-15 and defer Zhihu to 2026-08-16.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional env file containing WECHAT_APPID/WECHAT_SECRET only used keys",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "data/growth/wechat-draft-inspection-2026-08-15.json",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=ROOT / "docs/reports/wechat-draft-inspection-2026-08-15.md",
    )
    parser.add_argument("--dry-run-payload", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.dry_run_payload:
        api_payload = json.loads(args.dry_run_payload.read_text(encoding="utf-8"))
    else:
        app_id, secret = _load_wechat_env(args.env_file)
        client = WechatClient(app_id, secret)
        try:
            api_payload = _paginate_drafts(client)
        except WechatAPIError as exc:
            print(f"WeChat API error: {exc}", file=sys.stderr)
            return 2

    report = inspect_draft_payload(api_payload)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.md_out.write_text(render_markdown_report(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "total_count": report.get("total_count"),
                "item_count": report.get("item_count"),
                "overlap_count": len(report.get("plan_overlap") or []),
                "json_out": str(args.json_out),
                "md_out": str(args.md_out),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
