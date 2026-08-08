"""Channel preview renderers — Website / WeChat artifacts only (no publisher calls)."""

from __future__ import annotations

import json
from pathlib import Path

from content.fingerprint import compute_content_fingerprint
from content.models import ContentCandidate, ContentType, EditorialStatus
from content.store import load_content_config
from utils.helpers import now_iso

APPROVED_MEDIA = "approved"


class RenderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _require_renderable(candidate: ContentCandidate) -> dict:
    gate = candidate.gate_result or {}
    if not gate.get("passed"):
        raise RenderError("GATE_NOT_PASS", "Hard Gate must PASS before channel render")
    if candidate.editorial_status is not EditorialStatus.APPROVED:
        raise RenderError(
            "EDITORIAL_NOT_APPROVED",
            "Editorial APPROVED required before channel render",
        )
    draft = candidate.draft or candidate.metadata.get("structured_draft")
    if not draft:
        raise RenderError("DRAFT_MISSING", "Structured draft required for render")
    return draft if isinstance(draft, dict) else draft.to_dict()


def _media_refs(candidate: ContentCandidate) -> list[dict]:
    images = candidate.metadata.get("images_metadata") or {}
    refs: list[dict] = []
    if isinstance(images, dict):
        items = images.get("items") or images.get("media") or []
        if isinstance(images, dict) and images.get("status") == APPROVED_MEDIA:
            refs.append(dict(images))
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").lower() != APPROVED_MEDIA:
                continue
            refs.append(item)
    return refs


def _route_for(candidate: ContentCandidate) -> str:
    if candidate.content_type is ContentType.INSIGHT:
        return f"/insight/{candidate.slug}"
    return f"/daily/{candidate.slug}"


def _fingerprint(candidate: ContentCandidate, draft: dict) -> str:
    return compute_content_fingerprint(
        content_id=candidate.content_id,
        content_type=candidate.content_type.value,
        draft=draft,
        claim_ids=list(candidate.claim_ids),
        source_ids=list(candidate.source_document_ids),
    )


def render_website_preview(
    candidate: ContentCandidate,
    *,
    base_dir: str | Path | None = None,
) -> dict:
    """Write Website preview artifact under dist/review/channel/website/<content_id>/."""
    draft = _require_renderable(candidate)
    cfg = load_content_config()
    root = Path(
        base_dir
        or (cfg.get("paths") or {}).get("channel_website")
        or "dist/review/channel/website"
    )
    out_dir = root / candidate.content_id
    out_dir.mkdir(parents=True, exist_ok=True)

    fp = _fingerprint(candidate, draft)
    route = _route_for(candidate)
    media = _media_refs(candidate)

    statements = draft.get("statements") or []
    body_lines = []
    for stmt in statements:
        text = stmt.get("text") if isinstance(stmt, dict) else str(stmt)
        body_lines.append(text)
    body_md = "\n\n".join(body_lines)

    frontmatter = {
        "content_id": candidate.content_id,
        "content_type": candidate.content_type.value,
        "slug": candidate.slug,
        "title": draft.get("title") or candidate.primary_signal,
        "summary": draft.get("summary") or candidate.research_question,
        "published_at": candidate.metadata.get("published_at") or "",
        "status": "preview",
        "editorial_gate": "passed" if (candidate.gate_result or {}).get("passed") else "failed",
        "gate_status": "passed",
        "hard_gate_status": "passed",
        "editorial_review_status": candidate.editorial_status.value.lower(),
        "claim_provenance": {
            "claim_ids": list(candidate.claim_ids),
            "evidence_ids": list(candidate.evidence_ids),
            "source_document_ids": list(candidate.source_document_ids),
        },
        "route": route,
        "content_fingerprint": fp,
        "visibility": "private",
        "type": candidate.content_type.value,
    }

    # MDX with YAML-like frontmatter
    fm_lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, (dict, list)):
            fm_lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            fm_lines.append(f'{key}: "{value}"')
    fm_lines.append("---")
    mdx = "\n".join(fm_lines) + "\n\n" + f"# {frontmatter['title']}\n\n{body_md}\n"

    article_path = out_dir / "article.mdx"
    article_path.write_text(mdx, encoding="utf-8")

    metadata = {
        "content_id": candidate.content_id,
        "content_type": candidate.content_type.value,
        "slug": candidate.slug,
        "route": route,
        "channel": "website",
        "content_fingerprint": fp,
        "media": media,
        "rendered_at": now_iso(),
        "published": False,
        "status": "preview",
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "channel": "website",
        "ok": True,
        "publisher_invoked": False,
        "route": route,
        "content_fingerprint": fp,
        "artifact_dir": str(out_dir),
        "files": ["article.mdx", "metadata.json", "render-report.json"],
    }
    (out_dir / "render-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    candidate.metadata["website_artifact"] = metadata
    candidate.metadata["website_artifact_dir"] = str(out_dir)
    return {"artifact_dir": str(out_dir), "metadata": metadata, "report": report}


def render_wechat_preview(
    candidate: ContentCandidate,
    *,
    base_dir: str | Path | None = None,
) -> dict:
    """Write WeChat preview HTML artifact — never calls draft/freepublish APIs."""
    draft = _require_renderable(candidate)
    cfg = load_content_config()
    root = Path(
        base_dir
        or (cfg.get("paths") or {}).get("channel_wechat")
        or "dist/review/channel/wechat"
    )
    out_dir = root / candidate.content_id
    out_dir.mkdir(parents=True, exist_ok=True)

    fp = _fingerprint(candidate, draft)
    media = _media_refs(candidate)
    title = draft.get("title") or candidate.primary_signal
    statements = draft.get("statements") or []

    parts = [
        f"<article data-content-id=\"{candidate.content_id}\" "
        f"data-content-type=\"{candidate.content_type.value}\">",
        f"<h1>{title}</h1>",
    ]
    for stmt in statements:
        text = stmt.get("text") if isinstance(stmt, dict) else str(stmt)
        stype = (stmt.get("statement_type") or stmt.get("kind") or "") if isinstance(stmt, dict) else ""
        parts.append(f'<section data-statement-type="{stype}"><p>{text}</p></section>')
    parts.append("<footer>ZeroRealm Preview — not published</footer>")
    parts.append("</article>")
    html = "\n".join(parts)

    (out_dir / "article.html").write_text(html, encoding="utf-8")
    metadata = {
        "content_id": candidate.content_id,
        "content_type": candidate.content_type.value,
        "slug": candidate.slug,
        "channel": "wechat",
        "content_fingerprint": fp,
        "media": media,
        "rendered_at": now_iso(),
        "published": False,
        "status": "preview",
        "title": title,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "channel": "wechat",
        "ok": True,
        "publisher_invoked": False,
        "freepublish": False,
        "draft_api": False,
        "content_fingerprint": fp,
        "artifact_dir": str(out_dir),
        "files": ["article.html", "metadata.json", "render-report.json"],
    }
    (out_dir / "render-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    candidate.metadata["wechat_artifact"] = metadata
    candidate.metadata["wechat_artifact_dir"] = str(out_dir)
    return {"artifact_dir": str(out_dir), "metadata": metadata, "report": report}


def render_channels(candidate: ContentCandidate) -> dict:
    website = render_website_preview(candidate)
    wechat = render_wechat_preview(candidate)
    return {"website": website, "wechat": wechat, "publisher_invoked": False}
