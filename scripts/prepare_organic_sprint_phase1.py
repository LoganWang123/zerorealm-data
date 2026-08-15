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
    CONVERSION_FUNNEL_ZH,
    IMAGE_STATUS,
    OPS_DATE,
    POINT_CONTRIBUTION_DATE,
    POINT_CONTRIBUTION_PIECE_ID,
    POINT_CONTRIBUTION_TITLE,
    SAME_CHANNEL_TOPIC_WINDOW_DAYS,
    STATUS_CANCELED,
    STATUS_CONFIGURED,
    STATUS_DELETED,
    STATUS_DRAFT_SAVED,
    WECHAT_AUTOREPLY_PIECE_ID,
    WECHAT_TIEKU_CANCEL_REASON,
    WECHAT_TIEKU_DATE,
    WECHAT_TIEKU_PIECE_ID,
    WECHAT_TIEKU_TITLE,
    ZHIHU_CTA_LEAD_IN_ZH,
    ZHIHU_DATE,
    ZHIHU_DRAFT_ID,
    ZHIHU_REVISION_REASON,
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
        f"- External API mutation (repo): `{manifest['safety']['external_wechat_zhihu_mutation']}`",
        f"- Browser manual ops: `{manifest['safety'].get('browser_manual_ops', True)}`",
        f"- LLM API: `{manifest['safety']['llm_api']}`",
        "- Friends circle / groups / private: forbidden",
        "- Secrets policy: no CDN URLs / login tokens / cookies recorded; "
        "no Antigravity account/email or quota recovery clock",
        f"- Conversion: `{CONVERSION_FUNNEL_ZH}；可公开订阅，无一对一/加微信/访谈`",
        "- Professional boundaries: declared in packet compliance",
        "- Truthfulness: WeChat autoreply `configured`/`enabled`; "
        f"缺货贴图计划 `{STATUS_CANCELED}` "
        f"(`{WECHAT_TIEKU_CANCEL_REASON}`；草稿/5图/provenance 保留)；"
        "单点贡献稿 `production_ready_revision` / `external_sync_pending`；"
        "Zhihu external draft accepted "
        f"(`{STATUS_DRAFT_SAVED}`, `revision_pending=false`, `publish_blocked=false`, "
        "`employment_boundary_synced=true`); "
        f"`legacy_interview_cta_status={STATUS_DELETED}`; "
        f"historical `{ZHIHU_REVISION_REASON}` resolved",
        "",
        "## Packets",
        "",
        f"1. **WeChat 单点贡献修订** `{POINT_CONTRIBUTION_DATE}` 《{POINT_CONTRIBUTION_TITLE}》",
        f"   - piece_id: `{POINT_CONTRIBUTION_PIECE_ID}`",
        "   - status: `production_ready_revision`",
        "   - external_sync_status: `external_sync_pending`（不得标已同步/已发布/已定时）",
        "   - packet: `data/growth/content-packet-o1-wechat-point-contribution-2026-08-15.json`",
        f"   - agy handoff: `docs/reports/wechat-point-contribution-revision-{OPS_DATE}.md`",
        "   - CTA: 回复「复盘表」打开周经营复盘工具",
        "",
        f"2. **WeChat 贴图（已取消发布计划）** `{WECHAT_TIEKU_DATE}` 《{WECHAT_TIEKU_TITLE}》",
        f"   - piece_id: `{WECHAT_TIEKU_PIECE_ID}`",
        f"   - tracking: `{wechat['cta']['tracking_id']}`",
        "   - packet: `data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json`",
        "   - image briefs: 5（保留；不删除）",
        "   - image_status: `images_ready`",
        f"   - external_status: `{STATUS_CANCELED}`",
        f"   - cancel_reason: `{WECHAT_TIEKU_CANCEL_REASON}`",
        f"   - draft_status: `{STATUS_DRAFT_SAVED}`（外部草稿保留）",
        "   - employment_boundary_synced: `true`",
        "   - scheduled / published: `false`",
        "",
        f"3. **Zhihu 场景改写** `{ZHIHU_DATE}` 《{ZHIHU_TITLE}》",
        f"   - piece_id: `{ZHIHU_SCENARIO_PIECE_ID}`",
        f"   - tracking: `{zhihu['cta']['tracking_id']}`",
        "   - packet: `data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json`",
        f"   - external draft id: `{ZHIHU_DRAFT_ID}`",
        f"   - external_status: `{STATUS_DRAFT_SAVED}`",
        "   - revision_pending: `false`",
        "   - employment_boundary_synced: `true`",
        "   - publish_blocked: `false`",
        f"   - legacy_interview_cta_status: `{STATUS_DELETED}`",
        f"   - CTA lead-in verified: `{ZHIHU_CTA_LEAD_IN_ZH}`",
        "",
        "4. **公众号欢迎语 + 关键词「复盘表」**",
        f"   - piece_id: `{WECHAT_AUTOREPLY_PIECE_ID}`",
        "   - packet: `data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json`",
        f"   - external_status: `{STATUS_CONFIGURED}` (enabled)",
        "   - employment_boundary_synced: `true`",
        "   - false Excel download claim: **no**",
        "",
        "## Schedule / ledger",
        "",
        f"- Approved organic-only schedule: `{manifest['schedule_path']}` "
        f"(approved={schedule.get('approved')})",
        f"- Experiment ledger overlay: `{manifest['ledger_path']}`",
        "- Manifest: `data/growth/organic-sprint-phase1-manifest-2026-08-15.json`",
        f"- Anti-duplication: same WeChat OA {SAME_CHANNEL_TOPIC_WINDOW_DAYS}d "
        f"core-question overlap → `{WECHAT_TIEKU_CANCEL_REASON}`",
        "- Rule: draft ≠ scheduled/published; `deleted` only for `legacy_interview_cta_status`",
        "",
        "## Continue / Stop",
        "",
    ]
    for item in manifest["continue_stop_metrics"]["continue_all_of"]:
        lines.append(f"- Continue · `{item['id']}`: {item['rule']}")
    for item in manifest["continue_stop_metrics"]["stop_any_of"]:
        lines.append(f"- Stop · `{item['id']}`: {item['action']}")
    lines.extend(["", "## Browser handoff", ""])
    for step in manifest["browser_handoff"]["steps"]:
        lines.append(f"{step['order']}. ({step['surface']}) {step['action']}")
    lines.extend(
        [
            "",
            "## Antigravity",
            "",
            "- Bitmap images: **images_ready**（缺货贴图 5 张保留；发布计划 canceled）",
            "- Cursor prepared revision + briefs only; do not generate bitmaps here.",
            "- Point-contribution: Agy browser sync only; no WeChat backend publish.",
            "",
        ]
    )
    _ = autoreply
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
    zhihu_seed = build_zhihu_scenario_packet(body_markdown=zhihu_md_template)
    zhihu_body = zhihu_md_template.replace("CTA_URL_PLACEHOLDER", zhihu_seed["cta"]["url"])
    zhihu = build_zhihu_scenario_packet(body_markdown=zhihu_body)
    autoreply = build_wechat_autoreply_packet()

    # Preserve already-accepted image hashes/paths before building manifest.
    committed_wechat = json.loads(
        (
            ROOT / "data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json"
        ).read_text(encoding="utf-8")
    )
    committed_zhihu = json.loads(
        (
            ROOT
            / "data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json"
        ).read_text(encoding="utf-8")
    )
    wechat["image_briefs"] = committed_wechat["image_briefs"]
    wechat["image_status"] = "images_ready"
    zhihu["image_briefs"] = committed_zhihu["image_briefs"]
    zhihu["image_status"] = "images_ready"
    for key in (
        "external_status",
        "draft_status",
        "assets_status",
        "employment_boundary_synced",
        "publish_blocked",
        "block_reason",
        "revision_pending",
        "local_packet_corrected",
        "legacy_interview_cta_status",
        "scheduled",
        "published",
    ):
        if key in committed_zhihu:
            zhihu[key] = committed_zhihu[key]

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

    template_path = ROOT / "data/growth/experiment-ledger.template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    organic_note = (
        "2026-08-15 organic sprint phase 1: point-contribution revision "
        "(production_ready_revision/external_sync_pending) + "
        f"OA 贴图 {WECHAT_TIEKU_DATE} canceled "
        f"({WECHAT_TIEKU_CANCEL_REASON}) + Zhihu {ZHIHU_DATE} + "
        "welcome/keyword「复盘表」; organic-only; see "
        "data/growth/organic-only-schedule-2026-08-15.json."
    )
    template["notes"] = organic_note
    _write_json(template_path, template)

    print(
        json.dumps(
            {
                "status": manifest["status"],
                "manifest": "data/growth/organic-sprint-phase1-manifest-2026-08-15.json",
                "schedule": "data/growth/organic-only-schedule-2026-08-15.json",
                "ledger": "data/growth/organic-experiment-ledger-2026-08-15.json",
                "report": "docs/reports/organic-sprint-phase1-2026-08-15.md",
                "image_status": "images_ready",
                "wechat_tieku_status": STATUS_CANCELED,
                "cancel_reason": WECHAT_TIEKU_CANCEL_REASON,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
