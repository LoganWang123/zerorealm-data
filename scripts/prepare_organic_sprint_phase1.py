#!/usr/bin/env python3
"""Prepare organic sprint phase-1 packets (no LLM, no image gen, no publish)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth.organic_sprint_phase1 import (  # noqa: E402
    IMAGE_STATUS,
    OPS_DATE,
    WECHAT_AUTOREPLY_PIECE_ID,
    WECHAT_TIEKU_DATE,
    WECHAT_TIEKU_PIECE_ID,
    WECHAT_TIEKU_TITLE,
    ZHIHU_DATE,
    ZHIHU_SCENARIO_PIECE_ID,
    ZHIHU_TITLE,
    build_organic_experiment_ledger_update,
    build_organic_only_schedule,
    build_phase1_manifest,
    build_wechat_autoreply_packet,
    build_wechat_tieku_packet,
    build_zhihu_scenario_packet,
    normalize_markdown,
    validate_autoreply_packet,
    validate_schedule,
    validate_wechat_tieku_packet,
    validate_zhihu_packet,
)

ARTICLE_DIR = ROOT / "content" / "organic_packets" / OPS_DATE


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_md(name: str) -> str:
    return normalize_markdown((ARTICLE_DIR / name).read_text(encoding="utf-8"))


def render_report(
    *,
    manifest: dict,
    schedule: dict,
    wechat: dict,
    zhihu: dict,
    autoreply: dict,
) -> str:
    lines = [
        f"# Organic sprint phase 1 packets · {OPS_DATE}",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Image status: `{IMAGE_STATUS}`",
        f"- External mutation: `{manifest['safety']['external_wechat_zhihu_mutation']}`",
        f"- LLM API: `{manifest['safety']['llm_api']}`",
        f"- Friends circle / groups / private: forbidden",
        "",
        "## Packets",
        "",
        f"1. **WeChat 贴图** `{WECHAT_TIEKU_DATE}` 《{WECHAT_TIEKU_TITLE}》",
        f"   - piece_id: `{WECHAT_TIEKU_PIECE_ID}`",
        f"   - tracking: `{wechat['cta']['tracking_id']}`",
        f"   - packet: `{manifest['packets'][0]['packet_json']}`",
        "   - image briefs: 5（1:1 方封面 + 4×4:5 竖屏合步：1-2 / 3-4 / 5-6 / 7）",
        "",
        f"2. **Zhihu 场景改写** `{ZHIHU_DATE}` 《{ZHIHU_TITLE}》",
        f"   - piece_id: `{ZHIHU_SCENARIO_PIECE_ID}`",
        f"   - tracking: `{zhihu['cta']['tracking_id']}`",
        f"   - packet: `{manifest['packets'][1]['packet_json']}`",
        "",
        f"3. **公众号欢迎语 + 关键词「复盘表」**",
        f"   - piece_id: `{WECHAT_AUTOREPLY_PIECE_ID}`",
        f"   - packet: `{manifest['packets'][2]['packet_json']}`",
        f"   - false Excel download claim: **no**",
        "",
        "## Schedule / ledger",
        "",
        f"- Approved organic-only schedule: `{manifest['schedule_path']}` "
        f"(approved={schedule.get('approved')})",
        f"- Experiment ledger overlay: `{manifest['ledger_path']}`",
        "",
        "## Continue / Stop",
        "",
    ]
    for item in manifest["continue_stop_metrics"]["continue_all_of"]:
        lines.append(f"- Continue · `{item['id']}`: {item['rule']}")
    for item in manifest["continue_stop_metrics"]["stop_any_of"]:
        lines.append(f"- Stop · `{item['id']}`: {item['action']}")
    lines.extend(
        [
            "",
            "## Browser handoff",
            "",
        ]
    )
    for step in manifest["browser_handoff"]["steps"]:
        lines.append(f"{step['order']}. ({step['surface']}) {step['action']}")
    lines.extend(
        [
            "",
            "## Antigravity",
            "",
            f"- Bitmap images: **{IMAGE_STATUS}**",
            "- Cursor prepared image briefs only; do not generate bitmaps in this phase.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate existing committed artifacts without rewriting",
    )
    args = parser.parse_args()

    source_paths = {
        WECHAT_TIEKU_PIECE_ID: (
            f"content/organic_packets/{OPS_DATE}/o1-wechat-stockout-tieku.md"
        ),
        ZHIHU_SCENARIO_PIECE_ID: (
            f"content/organic_packets/{OPS_DATE}/o1-zhihu-inventory-stockout.md"
        ),
        WECHAT_AUTOREPLY_PIECE_ID: (
            f"content/organic_packets/{OPS_DATE}/o1-wechat-autoreply-fupan.md"
        ),
    }

    wechat_md = _read_md("o1-wechat-stockout-tieku.md")
    zhihu_md_template = _read_md("o1-zhihu-inventory-stockout.md")

    wechat = build_wechat_tieku_packet(body_markdown=wechat_md)
    # Resolve Zhihu CTA first so the body embeds the final trackable URL once.
    zhihu_seed = build_zhihu_scenario_packet(body_markdown=zhihu_md_template)
    zhihu_body = zhihu_md_template.replace("CTA_URL_PLACEHOLDER", zhihu_seed["cta"]["url"])
    zhihu = build_zhihu_scenario_packet(body_markdown=zhihu_body)
    autoreply = build_wechat_autoreply_packet()
    schedule = build_organic_only_schedule(
        wechat_packet=wechat,
        zhihu_packet=zhihu,
        autoreply_packet=autoreply,
    )
    ledger = build_organic_experiment_ledger_update()
    manifest = build_phase1_manifest(
        wechat_packet=wechat,
        zhihu_packet=zhihu,
        autoreply_packet=autoreply,
        schedule=schedule,
        article_source_paths=source_paths,
    )

    validate_wechat_tieku_packet(wechat)
    validate_zhihu_packet(zhihu)
    validate_autoreply_packet(autoreply)
    validate_schedule(schedule)

    if args.check:
        print("organic sprint phase1 validation OK")
        return 0

    _write_json(
        ROOT / "data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json",
        wechat,
    )
    _write_json(
        ROOT / "data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json",
        zhihu,
    )
    _write_json(
        ROOT / "data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json",
        autoreply,
    )
    _write_json(ROOT / "data/growth/organic-only-schedule-2026-08-15.json", schedule)
    _write_json(ROOT / "data/growth/organic-experiment-ledger-2026-08-15.json", ledger)
    _write_json(
        ROOT / "data/growth/organic-sprint-phase1-manifest-2026-08-15.json",
        manifest,
    )

    report_md = ROOT / "docs/reports/organic-sprint-phase1-2026-08-15.md"
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(
        render_report(
            manifest=manifest,
            schedule=schedule,
            wechat=wechat,
            zhihu=zhihu,
            autoreply=autoreply,
        ),
        encoding="utf-8",
    )

    # Keep founder experiment ledger template notes aligned with organic sprint.
    template_path = ROOT / "data/growth/experiment-ledger.template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    organic_note = (
        "2026-08-15 organic sprint phase 1 approved: OA 贴图 2026-08-17《柜机缺货先查这7步》"
        " + Zhihu 2026-08-18《库存显示有货，为什么柜机还是缺货？》"
        " + welcome/keyword「复盘表」config; organic-only (no朋友圈/groups/private);"
        " see data/growth/organic-only-schedule-2026-08-15.json and"
        " data/growth/organic-experiment-ledger-2026-08-15.json."
    )
    existing = str(template.get("notes") or "")
    if "organic sprint phase 1" not in existing:
        template["notes"] = (existing.rstrip() + " " + organic_note).strip()
        _write_json(template_path, template)

    print(
        json.dumps(
            {
                "status": manifest["status"],
                "manifest": "data/growth/organic-sprint-phase1-manifest-2026-08-15.json",
                "schedule": "data/growth/organic-only-schedule-2026-08-15.json",
                "ledger": "data/growth/organic-experiment-ledger-2026-08-15.json",
                "report": "docs/reports/organic-sprint-phase1-2026-08-15.md",
                "image_status": IMAGE_STATUS,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
