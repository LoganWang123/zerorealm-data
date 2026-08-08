"""Publisher preflight / dry-run — never calls WeChat API or writes production website."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from content.models import ContentType
from content.release_candidate import (
    ReleaseCandidate,
    ReleaseCandidateError,
    ReleaseCandidateStatus,
    assert_ready_for_publish,
)
from utils.helpers import now_iso


def _artifact_hash(artifact: dict) -> str:
    raw = json.dumps(artifact or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def website_target_route(rc: ReleaseCandidate) -> str:
    if rc.content_type == ContentType.INSIGHT.value or rc.content_type == "insight":
        return f"/insight/{rc.slug}"
    if rc.content_type == ContentType.DAILY.value or rc.content_type == "daily":
        return f"/daily/{rc.slug}"
    raise ReleaseCandidateError(
        "CONTENT_TYPE_MISMATCH",
        f"Unknown content_type for website route: {rc.content_type}",
    )


def build_website_publish_plan(rc: ReleaseCandidate) -> dict:
    """Dry-run Website publish plan. Does not write production repo / commit / push / deploy."""
    assert_ready_for_publish(rc)
    route = website_target_route(rc)
    # Hard identity rule: Insight never maps to Daily route.
    if rc.content_type == "insight" and route.startswith("/daily/"):
        raise ReleaseCandidateError(
            "CONTENT_TYPE_MISMATCH",
            "Insight Release Candidate cannot publish to Daily route",
        )
    plan = {
        "channel": "website",
        "mode": "dry-run",
        "content_id": rc.content_id,
        "content_type": rc.content_type,
        "slug": rc.slug,
        "target_route": route,
        "artifact": dict(rc.website_artifact),
        "artifact_hash": _artifact_hash(rc.website_artifact),
        "content_fingerprint": rc.content_fingerprint,
        "content_hash": rc.content_fingerprint,
        "expected_git_changes": [
            f"content/{rc.content_type}/{rc.slug}.mdx",
        ],
        "network_calls": [],
        "writes_production": False,
        "commits": False,
        "pushes": False,
        "deploys": False,
        "generated_at": now_iso(),
        "release_candidate_id": rc.release_candidate_id,
        "status_required": ReleaseCandidateStatus.READY_FOR_PUBLISH.value,
    }
    return plan


def build_wechat_publish_plan(rc: ReleaseCandidate) -> dict:
    """Dry-run WeChat publish plan. Never create draft / upload / freepublish / 群发."""
    assert_ready_for_publish(rc)
    plan = {
        "channel": "wechat",
        "mode": "dry-run",
        "content_id": rc.content_id,
        "title": (rc.wechat_artifact or {}).get("title") or rc.slug,
        "artifact": dict(rc.wechat_artifact),
        "artifact_hash": _artifact_hash(rc.wechat_artifact),
        "media": list((rc.wechat_artifact or {}).get("media") or []),
        "content_fingerprint": rc.content_fingerprint,
        "api_calls": [],
        "create_draft": False,
        "upload": False,
        "freepublish": False,
        "mass_send": False,
        "network_calls": [],
        "generated_at": now_iso(),
        "release_candidate_id": rc.release_candidate_id,
        "status_required": ReleaseCandidateStatus.READY_FOR_PUBLISH.value,
    }
    return plan


def build_release_preflight(
    rc: ReleaseCandidate,
    *,
    out_dir: str | Path | None = None,
) -> dict:
    """Write dry-run plans under dist/review/release-plan/<rc-id>/ (runtime only)."""
    website = build_website_publish_plan(rc)
    wechat = build_wechat_publish_plan(rc)
    release = {
        "release_candidate_id": rc.release_candidate_id,
        "content_id": rc.content_id,
        "content_type": rc.content_type,
        "slug": rc.slug,
        "status": rc.status.value,
        "content_fingerprint": rc.content_fingerprint,
        "website_plan": website,
        "wechat_plan": wechat,
        "dry_run": True,
        "publisher_invoked": False,
        "wechat_api_called": False,
        "website_production_written": False,
        "generated_at": now_iso(),
    }
    root = Path(out_dir or f"dist/review/release-plan/{rc.release_candidate_id}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "website-plan.json").write_text(
        json.dumps(website, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "wechat-plan.json").write_text(
        json.dumps(wechat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "release-plan.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    release["artifact_dir"] = str(root)
    return release


def publisher_invoke_guard(rc: ReleaseCandidate | dict, *, dry_run: bool = True) -> dict:
    """Single entry used by future publishers. Real publish remains blocked."""
    assert_ready_for_publish(rc)
    if not dry_run:
        raise ReleaseCandidateError(
            "PUBLISH_DISABLED",
            "Real channel publish is disabled in this build; use dry-run only",
        )
    obj = rc if isinstance(rc, ReleaseCandidate) else ReleaseCandidate.from_dict(rc)
    return build_release_preflight(obj)
