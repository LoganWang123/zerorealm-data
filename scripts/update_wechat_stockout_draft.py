#!/usr/bin/env python3
"""Update the authorized w1-wechat-stockout WeChat draft to Chinese-only copy.

Safety:
- Relists drafts and preserves the unrelated single-point-contribution draft.
- Calls official draft/update only on STOCKOUT_MEDIA_ID.
- Reuses live cover thumb + body illustration (no image generation or re-upload).
- Reads back via draft/get.
- Never delete / freepublish / mass-send, and never create a second draft.
- Never prints credentials.
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
    STOCKOUT_MEDIA_ID,
    apply_wechat_draft_created,
    evidence_public_view,
    list_all_drafts,
    load_wechat_env,
    update_authorized_stockout_draft,
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


class StockoutUpdateWechatClient:
    """Adapter that exposes only list / get / official draft/update."""

    def __init__(self, inner: WechatClient):
        self._inner = inner

    def list_drafts(self, *, offset: int = 0, count: int = 20, no_content: int = 0) -> dict:
        return self._inner.list_drafts(offset=offset, count=count, no_content=no_content)

    def get_draft(self, media_id: str) -> dict:
        return self._inner.get_draft(media_id)

    def upload_permanent_image(self, path: str) -> dict:
        """Re-upload the existing local cover if WeChat omitted thumb_media_id."""
        return self._inner.upload_permanent_image(path)

    def update_draft(self, media_id: str, index: int, article: dict) -> dict:
        if media_id != STOCKOUT_MEDIA_ID:
            raise RuntimeError("refusing WeChat draft/update for a non-stockout media_id")
        return self._inner.update_draft(media_id, index, article)


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
        f"- Author: {result.get('author')}",
        f"- media_id prefix: `{prefix}`",
        f"- Updated this run: **{str(result.get('updated')).lower()}**",
        "- Official API: `draft/update` on the stockout media_id only",
        "- Visible text: **Chinese-only** (href/src UTM may remain hidden)",
        "",
        "## Safety",
        "",
        "- delete / publish / mass-send: **not performed**",
        "- unrelated draft overwrite: **not performed**",
        "- LLM API: **not called**",
        "- image generation / re-upload: **not performed**",
        "",
        "## Preserved unrelated draft",
        "",
        f"- title: {unrelated.get('title')}",
        f"- present before: {unrelated.get('present_before')}",
        f"- present after: {unrelated.get('present_after')}",
        "",
        "## Pre-update visible-text inspection",
        "",
    ]
    pre = (result.get("pre_update") or {}).get("visible_text") or {}
    lines.extend(
        [
            f"- previous author: {(result.get('pre_update') or {}).get('author')}",
            f"- previous visible Latin token count: {pre.get('visible_latin_count')}",
            f"- previous raw URL visible: {pre.get('raw_url_visible')}",
            f"- illustration reused: {(result.get('illustration') or {}).get('reused')}",
            f"- existing cover re-uploaded (no generation): {result.get('cover_reuploaded')}",
            "",
            "## Readback",
            "",
        ]
    )
    readback = result.get("readback") or {}
    if readback:
        for key, value in readback.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append(f"- {result.get('message')}")
    lines.extend(
        [
            "",
            "## Post-update draft list",
            "",
            f"- total_count: **{inspection.get('total_count')}**",
            f"- item_count: **{inspection.get('item_count')}**",
            "",
        ]
    )
    return "\n".join(lines)


def _update_packets_report(manifest: dict, wechat_packet: dict) -> None:
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
        f"   - Author: `{(wechat_packet.get('draft') or {}).get('author')}`",
        "   - Visible text: Chinese-only for domestic readers; href/src UTM remain hidden",
        f"   - Evidence: `data/growth/evidence/2026-08-15/{PIECE_ID}/`",
        f"   - CTA href: `{wechat_packet['cta']['url']}`",
        "",
        "## Compliance",
        "",
        "- Single tool-page CTA + UTM per article (no raw URL shown)",
        "- No auto-publish / mass-send / delete",
        "- Official draft/update only on the stockout media_id",
        "- Unrelated single-point-contribution draft preserved",
        "- Bitmap images: **images_ready** (reused; Cursor did not generate)",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--packet", type=Path, default=PACKET_PATH)
    parser.add_argument("--media-id", default=STOCKOUT_MEDIA_ID)
    args = parser.parse_args(argv)

    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    app_id, secret = load_wechat_env(args.env_file)
    inner = WechatClient(app_id, secret)
    client = StockoutUpdateWechatClient(inner)

    try:
        listed = list_all_drafts(client)
        result = update_authorized_stockout_draft(
            client,
            packet=packet,
            media_id=args.media_id,
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
                "updated": result.get("updated"),
                "author": result.get("author"),
                "media_id_prefix": (str(result.get("media_id") or "")[:10] + "…"),
                "total_count": inspection.get("total_count"),
                "preserved_unrelated": (result.get("preserved_unrelated") or {}).get(
                    "present_after"
                ),
                "visible_text_chinese_only": (result.get("readback") or {}).get(
                    "visible_text_chinese_only"
                ),
                "evidence": str(EVIDENCE_DIR / "verification.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result.get("status") == "wechat_draft_updated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
