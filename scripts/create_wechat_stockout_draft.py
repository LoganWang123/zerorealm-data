#!/usr/bin/env python3
"""Create the authorized w1-wechat-stockout WeChat draft (draft-only).

Safety:
- Relists drafts, preserves the unrelated single-point-contribution draft.
- Blocks exact-title duplicates (no overwrite).
- Uploads cover/body images, calls draft/add, reads back via draft/get.
- Never delete / update / freepublish / mass-send.
- Never generates images or prints credentials.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.content_ops_phase1 import inspect_draft_payload  # noqa: E402
from growth.wechat_stockout_draft import (  # noqa: E402
    PIECE_ID,
    apply_wechat_draft_created,
    create_authorized_stockout_draft,
    evidence_public_view,
    list_all_drafts,
    load_wechat_env,
)
from publishing.wechat.client import WechatAPIError, WechatClient  # noqa: E402

_inspect_spec = importlib.util.spec_from_file_location(
    "inspect_wechat_drafts", ROOT / "scripts" / "inspect_wechat_drafts.py"
)
_inspect_mod = importlib.util.module_from_spec(_inspect_spec)
assert _inspect_spec.loader is not None
_inspect_spec.loader.exec_module(_inspect_mod)
render_markdown_report = _inspect_mod.render_markdown_report

PACKET_PATH = ROOT / "data/growth/content-packet-w1-wechat-stockout-2026-08-15.json"
MANIFEST_PATH = ROOT / "data/growth/content-ops-phase1-manifest-2026-08-15.json"
INSPECT_JSON = ROOT / "data/growth/wechat-draft-inspection-2026-08-15.json"
INSPECT_MD = ROOT / "docs/reports/wechat-draft-inspection-2026-08-15.md"
REPORT_MD = ROOT / "docs/reports/content-ops-phase1-packets-2026-08-15.md"
DRAFT_REPORT_MD = ROOT / "docs/reports/wechat-stockout-draft-2026-08-15.md"
EVIDENCE_DIR = ROOT / "data/growth/evidence/2026-08-15" / PIECE_ID


class DraftOnlyWechatClient:
    """Adapter that exposes only authorized draft/list/upload methods."""

    def __init__(self, inner: WechatClient):
        self._inner = inner

    def list_drafts(self, *, offset: int = 0, count: int = 20, no_content: int = 0) -> dict:
        return self._inner.list_drafts(offset=offset, count=count, no_content=no_content)

    def upload_permanent_image(self, path: str) -> dict:
        return self._inner.upload_permanent_image(path)

    def upload_content_image(self, path: str) -> str:
        return self._inner.upload_content_image(path)

    def create_draft(self, articles: list[dict]) -> str:
        return self._inner.create_draft(articles)

    def get_draft(self, media_id: str) -> dict:
        return self._inner.get_draft(media_id)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_draft_report(result: dict, inspection: dict) -> str:
    mid = str(result.get("media_id") or "")
    prefix = (mid[:10] + "…") if len(mid) > 10 else mid
    unrelated = result.get("preserved_unrelated") or {}
    lines = [
        "# WeChat stockout draft · 2026-08-15",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Mode: **draft_only**",
        f"- Title: {result.get('title')}",
        f"- media_id prefix: `{prefix}`",
        f"- Created: **{str(result.get('created')).lower()}**",
        f"- Exact-title duplicate: **{str(result.get('exact_title_duplicate')).lower()}**",
        "",
        "## Safety",
        "",
        "- delete / overwrite / publish / mass-send: **not performed**",
        "- LLM API: **not called**",
        "- image generation: **not performed**",
        "",
        "## Preserved unrelated draft",
        "",
        f"- title: {unrelated.get('title')}",
        f"- present before: {unrelated.get('present_before')}",
        f"- present after: {unrelated.get('present_after')}",
        "",
        "## Readback",
        "",
    ]
    readback = result.get("readback") or {}
    if readback:
        for key, value in readback.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append(f"- {result.get('message')}")
    lines.extend(
        [
            "",
            "## Post-create draft list",
            "",
            f"- total_count: **{inspection.get('total_count')}**",
            f"- item_count: **{inspection.get('item_count')}**",
            "",
        ]
    )
    return "\n".join(lines)


def _update_packets_report(manifest: dict, wechat_packet: dict) -> None:
    text = REPORT_MD.read_text(encoding="utf-8") if REPORT_MD.is_file() else ""
    lines = [
        "# Content ops phase 1 packets · 2026-08-15",
        "",
        f"- Status: `{manifest.get('status')}`",
        f"- Owner: `{manifest.get('owner_github')}`",
        "- Image status: `images_ready`",
        "- LLM API used: **false**",
        "",
        "## Packets",
        "",
        "1. **Zhihu** `w1-zhihu-five-metrics` — 智能柜运营商每周该盯哪五个过程指标？ (**PUBLISHED**)",
        "   - Status: `zhihu_published`",
        "   - Published at: `2026-08-15 01:51:00+08:00`",
        "   - Public URL: `https://zhuanlan.zhihu.com/p/2071774951238121348`",
        "   - Evidence: `data/growth/evidence/2026-08-15/w1-zhihu-five-metrics/`",
        "   - CTA: `https://zerorealm.tech/tools/smart-cabinet-weekly-review?utm_source=zhihu&utm_medium=article&utm_campaign=founder14d_20260813&utm_content=five_metrics_qa`",
        "",
        f"2. **WeChat** `{wechat_packet['piece_id']}` — {wechat_packet['title']} (**DRAFT**)",
        f"   - Status: `{wechat_packet.get('status')}`",
        f"   - Draft media_id prefix: `{(str((wechat_packet.get('draft') or {}).get('media_id') or '')[:10] + '…') if (wechat_packet.get('draft') or {}).get('media_id') else ''}`",
        f"   - Author / digest / source URL: set on draft/add",
        f"   - Evidence: `data/growth/evidence/2026-08-15/{PIECE_ID}/`",
        f"   - CTA: `{wechat_packet['cta']['url']}`",
        "",
        "## Compliance",
        "",
        "- Single tool-page CTA + UTM per article",
        "- No auto-publish / mass-send / delete / overwrite",
        "- Exact-title duplicates blocked",
        "- Unrelated single-point-contribution draft preserved",
        "- Bitmap images: **images_ready** (Antigravity; Cursor did not generate)",
        "",
    ]
    if text and "Zhihu" in text:
        REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    else:
        REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument(
        "--packet",
        type=Path,
        default=PACKET_PATH,
    )
    args = parser.parse_args(argv)

    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    app_id, secret = load_wechat_env(args.env_file)
    inner = WechatClient(app_id, secret)
    client = DraftOnlyWechatClient(inner)

    try:
        listed = list_all_drafts(client)
        result = create_authorized_stockout_draft(
            client,
            packet=packet,
            root=ROOT,
            prelisted=listed,
        )
        post_listed = list_all_drafts(client)
    except WechatAPIError as exc:
        print(f"WeChat API error: {exc}", file=sys.stderr)
        return 2

    inspection = inspect_draft_payload(post_listed)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if result.get("html"):
        (EVIDENCE_DIR / "article.html").write_text(result["html"], encoding="utf-8")
    evidence = evidence_public_view(result)
    _write_json(EVIDENCE_DIR / "verification.json", evidence)
    _write_json(INSPECT_JSON, inspection)
    INSPECT_MD.write_text(render_markdown_report(inspection), encoding="utf-8")
    DRAFT_REPORT_MD.write_text(_render_draft_report(result, inspection), encoding="utf-8")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest, packet = apply_wechat_draft_created(
        manifest, packet, result=result, inspection=inspection
    )
    _write_json(MANIFEST_PATH, manifest)
    _write_json(PACKET_PATH, packet)
    _update_packets_report(manifest, packet)

    print(
        json.dumps(
            {
                "ok": True,
                "status": result.get("status"),
                "created": result.get("created"),
                "exact_title_duplicate": result.get("exact_title_duplicate"),
                "total_count": inspection.get("total_count"),
                "preserved_unrelated": (result.get("preserved_unrelated") or {}).get(
                    "present_after"
                ),
                "evidence": str(EVIDENCE_DIR / "verification.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result.get("status") in {"wechat_draft_created", "blocked_exact_title_duplicate"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
