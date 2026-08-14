#!/usr/bin/env python3
"""Prepare content-ops phase-1 production packets (no LLM, no image gen, no publish)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.content_ops_phase1 import (  # noqa: E402
    WECHAT_STOCKOUT_PIECE_ID,
    ZHIHU_PIECE_ID,
    build_phase1_manifest,
    build_wechat_stockout_packet,
    build_zhihu_five_metrics_packet,
    normalize_markdown,
)

ARTICLE_DIR = ROOT / "content" / "ops_packets" / "2026-08-15"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _export_runtime_package(packet: dict, slug: str) -> Path:
    """Write dist/content-package tree for local handoff (gitignored)."""
    out = ROOT / "dist" / "content-package" / slug
    for name in ("website", "wechat", "zhihu", "media", "sources"):
        (out / name).mkdir(parents=True, exist_ok=True)
    title = packet["title"]
    body = packet["body_markdown"]
    (out / "website" / "article.md").write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    channel = packet["channel"]
    if channel == "wechat":
        (out / "wechat" / "draft.md").write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    zhihu_pkg = {
        "title": title,
        "body": body,
        "excerpt": packet.get("excerpt", body[:120]),
        "topics": packet.get("topics") or packet.get("tags") or [],
        "sources": packet.get("sources") or [],
        "coverPrompt": packet.get("image_status"),
        "ctaUrl": packet["cta"]["url"],
        "autoPublish": False,
        "imageStatus": packet.get("image_status"),
    }
    (out / "zhihu" / "package.json").write_text(
        json.dumps(zhihu_pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    briefs = packet.get("image_briefs") or []
    pending = out / "media" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    (pending / "image-briefs.json").write_text(
        json.dumps(briefs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "sources" / "README.md").write_text(
        "\n".join(
            [
                f"# Sources · {slug}",
                "",
                f"- piece_id: `{packet['piece_id']}`",
                f"- cta: `{packet['cta']['url']}`",
                f"- image_status: `{packet.get('image_status')}`",
                "",
                "See committed packet JSON under data/growth/ for full provenance.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    metadata = {
        "slug": slug,
        "piece_id": packet["piece_id"],
        "channel": channel,
        "title": title,
        "cta_url": packet["cta"]["url"],
        "image_status": packet.get("image_status"),
        "autoPublish": False,
        "agnesImageGeneration": False,
    }
    (out / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out


def render_packets_report(
    *,
    manifest: dict,
    zhihu: dict,
    wechat: dict,
) -> str:
    lines = [
        "# Content ops phase 1 packets · 2026-08-15",
        "",
        f"- Status: `{manifest.get('status')}`",
        f"- Owner: `{manifest.get('owner_github')}`",
        f"- Image status: `awaiting_antigravity_images`",
        f"- LLM API used: **false**",
        "",
        "## Packets",
        "",
        f"1. **Zhihu** `{zhihu['piece_id']}` — {zhihu['title']}",
        f"   - CTA: `{zhihu['cta']['url']}`",
        f"   - Tags: {', '.join(zhihu.get('tags') or [])}",
        f"   - Excerpt: {zhihu.get('excerpt')}",
        "",
        f"2. **WeChat** `{wechat['piece_id']}` — {wechat['title']}",
        f"   - Planned draft: `{wechat.get('planned_draft_date')}` / "
        f"publish `{wechat.get('planned_publish_date')}`",
        f"   - CTA: `{wechat['cta']['url']}`",
        f"   - Digest: {wechat.get('digest')}",
        "",
        "## Compliance",
        "",
        "- Single tool-page CTA + UTM per article",
        "- No auto-publish / mass-send",
        "- No fabricated industry benchmarks",
        "- Bitmap images: **awaiting_antigravity_images**",
        "",
        "## Files",
        "",
        "- `data/growth/content-ops-phase1-manifest-2026-08-15.json`",
        "- `data/growth/content-packet-w1-zhihu-five-metrics-2026-08-15.json`",
        "- `data/growth/content-packet-w1-wechat-stockout-2026-08-15.json`",
        "- `content/ops_packets/2026-08-15/w1-zhihu-five-metrics.md`",
        "- `content/ops_packets/2026-08-15/w1-wechat-stockout.md`",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inspection-json",
        type=Path,
        default=ROOT / "data/growth/wechat-draft-inspection-2026-08-15.json",
    )
    args = parser.parse_args(argv)

    zhihu_src = ARTICLE_DIR / "w1-zhihu-five-metrics.md"
    wechat_src = ARTICLE_DIR / "w1-wechat-stockout.md"
    zhihu_body = normalize_markdown(zhihu_src.read_text(encoding="utf-8"))
    wechat_body = normalize_markdown(wechat_src.read_text(encoding="utf-8"))

    zhihu_packet = build_zhihu_five_metrics_packet(body_markdown=zhihu_body)
    wechat_packet = build_wechat_stockout_packet(body_markdown=wechat_body)

    if args.inspection_json.is_file():
        inspection = json.loads(args.inspection_json.read_text(encoding="utf-8"))
    else:
        inspection = {
            "total_count": None,
            "item_count": None,
            "plan_overlap": [],
            "safety": {
                "delete": False,
                "overwrite": False,
                "publish": False,
                "mass_send": False,
                "llm_api": False,
                "image_generation": False,
            },
        }

    article_paths = {
        ZHIHU_PIECE_ID: str(zhihu_src.relative_to(ROOT)),
        WECHAT_STOCKOUT_PIECE_ID: str(wechat_src.relative_to(ROOT)),
    }
    manifest = build_phase1_manifest(
        inspection=inspection,
        zhihu_packet=zhihu_packet,
        wechat_packet=wechat_packet,
        article_source_paths=article_paths,
    )

    _write_json(
        ROOT / "data/growth/content-packet-w1-zhihu-five-metrics-2026-08-15.json",
        zhihu_packet,
    )
    _write_json(
        ROOT / "data/growth/content-packet-w1-wechat-stockout-2026-08-15.json",
        wechat_packet,
    )
    _write_json(ROOT / "data/growth/content-ops-phase1-manifest-2026-08-15.json", manifest)

    report_md = ROOT / "docs/reports/content-ops-phase1-packets-2026-08-15.md"
    report_md.write_text(
        render_packets_report(manifest=manifest, zhihu=zhihu_packet, wechat=wechat_packet),
        encoding="utf-8",
    )

    zhihu_dist = _export_runtime_package(zhihu_packet, ZHIHU_PIECE_ID)
    wechat_dist = _export_runtime_package(wechat_packet, WECHAT_STOCKOUT_PIECE_ID)

    print(
        json.dumps(
            {
                "ok": True,
                "manifest": "data/growth/content-ops-phase1-manifest-2026-08-15.json",
                "zhihu_dist": str(zhihu_dist),
                "wechat_dist": str(wechat_dist),
                "image_status": "awaiting_antigravity_images",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
