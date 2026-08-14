"""Authorized WeChat draft-only flow for w1-wechat-stockout.

Safety: list, upload media, draft/add, and draft/get only.
Never delete, overwrite, free-publish, or mass-send.
Never generate images or print credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any, Protocol

from growth.content_ops_phase1 import (
    PHASE1_DATE,
    WECHAT_STOCKOUT_PIECE_ID,
    inspect_draft_payload,
)
from growth.combat_pack import CAMPAIGN, TOOL_PAGE_URL

PIECE_ID = WECHAT_STOCKOUT_PIECE_ID
AUTHOR = "ZeroRealm AI"
STATUS_CREATED = "wechat_draft_created"
PRESERVED_UNRELATED_TITLE = "点位有销量却不赚钱？用一张周表算清单点贡献"
APPROVED_TITLE = "柜机缺货排查清单：先查这 7 步再补货"
DIGEST_MAX_BYTES = 120
ILLUSTRATION_MARKER_HEADING = "7 步排查"
CTA_HEADING = "唯一行动入口"

ZEROREALM_URL_RE = re.compile(r"https://zerorealm\.tech[^\s\"'<>]*")
INLINE_TOKEN_RE = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*)")


class DraftOnlyClient(Protocol):
    """Narrow WeChat surface: no delete / update / publish / mass-send."""

    def list_drafts(self, *, offset: int = 0, count: int = 20, no_content: int = 0) -> dict: ...

    def upload_permanent_image(self, path: str) -> dict: ...

    def upload_content_image(self, path: str) -> str: ...

    def create_draft(self, articles: list[dict]) -> str: ...

    def get_draft(self, media_id: str) -> dict: ...


class WechatDraftSafetyError(RuntimeError):
    """Raised when the authorized draft-only flow cannot proceed safely."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def truncate_utf8(value: str, max_bytes: int = DIGEST_MAX_BYTES) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_all_drafts(client: DraftOnlyClient, *, page_size: int = 20) -> dict:
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


def collect_titles(list_payload: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    for item in list_payload.get("item") or []:
        content = item.get("content") or {}
        for news in content.get("news_item") or []:
            title = str(news.get("title") or "").strip()
            if title:
                titles.append(title)
    return titles


def find_exact_title_item(list_payload: dict[str, Any], title: str) -> dict[str, Any] | None:
    for item in list_payload.get("item") or []:
        content = item.get("content") or {}
        for news in content.get("news_item") or []:
            if str(news.get("title") or "").strip() == title:
                return item
    return None


def preserved_unrelated_present(titles: list[str]) -> bool:
    return PRESERVED_UNRELATED_TITLE in titles


def count_cta_occurrences(html: str, cta_url: str) -> int:
    return unescape(html).count(cta_url)


def assert_single_approved_cta(html: str, cta_url: str) -> None:
    if not cta_url.startswith(TOOL_PAGE_URL):
        raise WechatDraftSafetyError("CTA is not the approved weekly-review tool page")
    if f"utm_campaign={CAMPAIGN}" not in cta_url:
        raise WechatDraftSafetyError("CTA is missing the approved campaign UTM")
    if "utm_content=stockout_checklist" not in cta_url:
        raise WechatDraftSafetyError("CTA is missing stockout_checklist utm_content")
    unescaped = unescape(html)
    found = ZEROREALM_URL_RE.findall(unescaped)
    if found != [cta_url]:
        raise WechatDraftSafetyError(
            "production HTML must contain exactly one approved weekly-review CTA/UTM"
        )
    if unescaped.count(cta_url) != 1:
        raise WechatDraftSafetyError("approved CTA URL must appear exactly once")
    if "mailto:" in unescaped or "hi@zerorealm.tech" in unescaped:
        raise WechatDraftSafetyError("second CTA / contact footer is not allowed")


def _inline(text: str) -> str:
    parts = INLINE_TOKEN_RE.split(text)
    rendered: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            rendered.append(
                '<code style="font-size:13px;background:#f1f5f9;padding:1px 4px;'
                f'border-radius:3px;">{escape(part[1:-1])}</code>'
            )
        elif part.startswith("**") and part.endswith("**") and len(part) >= 4:
            rendered.append(f"<strong>{escape(part[2:-2])}</strong>")
        else:
            rendered.append(escape(part))
    return "".join(rendered)


def _paragraph(html_inner: str) -> str:
    return (
        '<p style="margin:0 0 16px;font-size:16px;line-height:1.9;color:#334155;">'
        f"{html_inner}</p>"
    )


def _heading(level: int, text: str) -> str:
    if level == 2:
        return (
            '<div style="margin:34px 0 18px;padding-left:12px;border-left:4px solid #2563eb;">'
            f'<h2 style="margin:0;font-size:20px;line-height:1.5;color:#0f172a;">'
            f"{_inline(text)}</h2></div>"
        )
    return (
        f'<h3 style="margin:24px 0 12px;font-size:17px;line-height:1.6;color:#0f172a;">'
        f"{_inline(text)}</h3>"
    )


def _hr() -> str:
    return '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />'


def _blockquote(lines: list[str]) -> str:
    inner = "<br/>".join(_inline(line) for line in lines)
    return (
        '<blockquote style="margin:0 0 20px;padding:12px 14px;background:#f8fafc;'
        'border-left:4px solid #2563eb;color:#475569;font-size:14px;line-height:1.8;">'
        f"{inner}</blockquote>"
    )


def _list(items: list[tuple[str, str]], *, ordered: bool) -> str:
    tag = "ol" if ordered else "ul"
    rows = []
    for kind, text in items:
        prefix = "☐ " if kind == "check" else ""
        rows.append(
            '<li style="margin:0 0 8px;font-size:16px;line-height:1.8;color:#334155;">'
            f"{prefix}{_inline(text)}</li>"
        )
    return (
        f'<{tag} style="margin:0 0 18px;padding-left:22px;">{"".join(rows)}</{tag}>'
    )


def _table(rows: list[list[str]]) -> str:
    if len(rows) < 2:
        return ""
    header, body = rows[0], rows[2:] if _is_separator_row(rows[1]) else rows[1:]
    head_cells = "".join(
        '<th style="padding:8px 10px;border:1px solid #cbd5e1;background:#eff6ff;'
        f'font-size:14px;color:#0f172a;text-align:left;">{_inline(cell)}</th>'
        for cell in header
    )
    body_html = []
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        cells = "".join(
            '<td style="padding:8px 10px;border:1px solid #e2e8f0;font-size:14px;'
            f'color:#334155;">{_inline(cell)}</td>'
            for cell in padded[: len(header)]
        )
        body_html.append(f"<tr>{cells}</tr>")
    return (
        '<table style="width:100%;border-collapse:collapse;margin:0 0 18px;">'
        f"<thead><tr>{head_cells}</tr></thead>"
        f'<tbody>{"".join(body_html)}</tbody></table>'
    )


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _split_table_row(line: str) -> list[str]:
    raw = line.strip().strip("|")
    return [cell.strip() for cell in raw.split("|")]


def _illustration(url: str) -> str:
    return (
        '<p style="margin:24px 0 8px;">'
        f'<img src="{escape(url, quote=True)}" alt="缺货信号不等于真实缺货" '
        'style="display:block;width:100%;height:auto;" />'
        "</p>"
    )


def _cta_box(cta_url: str, copy: str) -> str:
    return (
        '<div style="margin:22px 0;padding:18px;background:#eff6ff;border:1px solid #bfdbfe;'
        'border-radius:8px;">'
        f'<p style="margin:0 0 10px;font-size:16px;line-height:1.8;font-weight:600;color:#0f172a;">'
        f"{escape(copy)}</p>"
        '<p style="margin:0;padding:12px;background:#2563eb;color:#ffffff;font-size:14px;'
        f'line-height:1.7;text-align:center;border-radius:6px;word-break:break-all;">'
        f"{cta_url}</p></div>"
    )


def build_stockout_html(
    markdown: str,
    *,
    illustration_url: str,
    cta_url: str,
    cta_copy: str,
) -> str:
    """Convert the stockout packet markdown into WeChat inline-CSS HTML."""
    if not illustration_url:
        raise WechatDraftSafetyError("illustration URL is required")
    lines = markdown.replace("\r\n", "\n").strip().split("\n")
    blocks: list[str] = []
    illustration_inserted = False
    cta_emitted = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue
        if stripped.startswith("# ") and not stripped.startswith("## "):
            i += 1
            continue
        if stripped == "---":
            blocks.append(_hr())
            i += 1
            continue
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if ILLUSTRATION_MARKER_HEADING in heading and not illustration_inserted:
                blocks.append(_illustration(illustration_url))
                illustration_inserted = True
            blocks.append(_heading(2, heading))
            if CTA_HEADING in heading:
                # Consume following copy + URL lines and emit the single CTA box.
                copy_parts: list[str] = []
                i += 1
                while i < len(lines):
                    nxt = lines[i].strip()
                    if nxt == "---" or nxt.startswith("#"):
                        break
                    if not nxt:
                        i += 1
                        continue
                    if nxt == cta_url:
                        i += 1
                        break
                    copy_parts.append(nxt)
                    i += 1
                copy = " ".join(copy_parts).strip() or cta_copy
                blocks.append(_cta_box(cta_url, copy))
                cta_emitted = True
                continue
            i += 1
            continue
        if stripped.startswith("### "):
            blocks.append(_heading(3, stripped[4:].strip()))
            i += 1
            continue
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].strip()).rstrip())
                i += 1
            blocks.append(_blockquote(quote_lines))
            continue
        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_table_row(lines[i]))
                i += 1
            blocks.append(_table(rows))
            continue
        if re.match(r"[-*] \[[ xX]\] ", stripped) or re.match(r"[-*] ", stripped) or re.match(
            r"\d+\. ", stripped
        ):
            ordered = bool(re.match(r"\d+\. ", stripped))
            items: list[tuple[str, str]] = []
            while i < len(lines):
                item_line = lines[i].strip()
                check = re.match(r"[-*] \[([ xX])\] (.+)$", item_line)
                bullet = re.match(r"[-*] (.+)$", item_line)
                number = re.match(r"\d+\. (.+)$", item_line)
                if check:
                    items.append(("check", check.group(2)))
                elif ordered and number:
                    items.append(("text", number.group(1)))
                elif (not ordered) and bullet and not check:
                    items.append(("text", bullet.group(1)))
                else:
                    break
                i += 1
            blocks.append(_list(items, ordered=ordered))
            continue
        if stripped == cta_url:
            if cta_emitted:
                raise WechatDraftSafetyError("duplicate CTA URL in markdown")
            blocks.append(_cta_box(cta_url, cta_copy))
            cta_emitted = True
            i += 1
            continue

        para_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith("#")
                or nxt.startswith(">")
                or nxt.startswith("|")
                or re.match(r"[-*] ", nxt)
                or re.match(r"\d+\. ", nxt)
                or nxt == cta_url
            ):
                break
            para_lines.append(nxt)
            i += 1
        blocks.append(_paragraph(_inline(" ".join(para_lines))))

    if not illustration_inserted:
        raise WechatDraftSafetyError("illustration was not inserted into production HTML")
    html = (
        '<div style="max-width:100%;padding:8px 4px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">'
        + "".join(blocks)
        + "</div>"
    )
    assert_single_approved_cta(html, cta_url)
    return html


def build_article_payload(
    *,
    title: str,
    html: str,
    thumb_media_id: str,
    digest: str,
    content_source_url: str,
    author: str = AUTHOR,
) -> dict[str, Any]:
    if not thumb_media_id:
        raise WechatDraftSafetyError("thumb_media_id is required")
    assert_single_approved_cta(html, content_source_url)
    return {
        "title": title,
        "author": author,
        "digest": truncate_utf8(digest),
        "content": html,
        "content_source_url": content_source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 1,
        "show_cover_pic": 1,
    }


def upload_body_image(client: DraftOnlyClient, path: str) -> str:
    """Upload a body image via WeChat APIs without mutating the local bitmap.

    Prefer ``uploadimg`` (CDN URL). If that rejects a large file, fall back to
    permanent image material and use the returned URL.
    """
    try:
        url = client.upload_content_image(path)
        if url:
            return url
    except Exception as first_error:
        uploaded = client.upload_permanent_image(path)
        url = str(uploaded.get("url") or "")
        if url:
            return url
        raise WechatDraftSafetyError(
            f"body image upload failed: {first_error}"
        ) from first_error
    uploaded = client.upload_permanent_image(path)
    url = str(uploaded.get("url") or "")
    if not url:
        raise WechatDraftSafetyError("body image upload returned no URL")
    return url


def verify_local_images(packet: dict[str, Any], root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    briefs = packet.get("image_briefs") or []
    for brief in briefs:
        purpose = brief.get("purpose")
        relative = brief.get("asset_path")
        expected = str(brief.get("sha256") or "")
        if purpose not in {"cover", "illustration"}:
            continue
        if not relative or not expected:
            raise WechatDraftSafetyError(f"image brief missing path/hash: {purpose}")
        path = root / relative
        if not path.is_file():
            raise WechatDraftSafetyError(f"Antigravity image missing: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise WechatDraftSafetyError(f"image hash mismatch for {purpose}")
        if brief.get("review_result") != "PASS":
            raise WechatDraftSafetyError(f"image review is not PASS: {purpose}")
        paths[purpose] = path
    if "cover" not in paths or "illustration" not in paths:
        raise WechatDraftSafetyError("cover and illustration images are required")
    return paths


def _has_body_illustration(content: str, illustration_url: str) -> bool:
    imgs = re.findall(
        r"<img[^>]+(?:data-src|src)=[\"']([^\"']+)",
        content,
    )
    if any("mmbiz.qpic.cn" in url for url in imgs):
        return True
    if illustration_url and (
        illustration_url in content or illustration_url.split("?")[0] in content
    ):
        return True
    return False


def verify_readback(
    stored_response: dict[str, Any],
    expected: dict[str, Any],
    *,
    illustration_url: str,
    require_uploaded_thumb: bool = True,
) -> dict[str, Any]:
    items = stored_response.get("news_item") if isinstance(stored_response, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise WechatDraftSafetyError("Draft readback did not return an article")
    stored = items[0]
    content = str(stored.get("content") or "")
    thumb_ok = (
        stored.get("thumb_media_id") == expected["thumb_media_id"]
        if require_uploaded_thumb
        else bool(stored.get("thumb_media_id"))
    )
    checks = {
        "title_match": stored.get("title") == expected["title"],
        "author_match": stored.get("author") == expected["author"],
        "digest_match": stored.get("digest") == expected["digest"],
        "source_url_match": stored.get("content_source_url") == expected["content_source_url"],
        "thumb_match": thumb_ok,
        "illustration_present": _has_body_illustration(content, illustration_url),
        "cta_count": count_cta_occurrences(content, expected["content_source_url"]),
    }
    if not checks["title_match"]:
        raise WechatDraftSafetyError("Draft readback title mismatch")
    if not checks["author_match"]:
        raise WechatDraftSafetyError("Draft readback author mismatch")
    if not checks["digest_match"]:
        raise WechatDraftSafetyError("Draft readback digest mismatch")
    if not checks["source_url_match"]:
        raise WechatDraftSafetyError("Draft readback source URL mismatch")
    if not checks["thumb_match"]:
        raise WechatDraftSafetyError("Draft readback cover mismatch")
    if not checks["illustration_present"]:
        raise WechatDraftSafetyError("Draft readback missing body illustration")
    assert_single_approved_cta(content, expected["content_source_url"])
    required = ["缺货信号", "7 步", "停止规则", "可打印清单"]
    missing = [fragment for fragment in required if fragment not in content]
    if missing:
        raise WechatDraftSafetyError("Draft readback is missing required content")
    return checks


def create_authorized_stockout_draft(
    client: DraftOnlyClient,
    *,
    packet: dict[str, Any],
    root: Path,
    prelisted: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the stockout draft or skip on exact-title duplicate. Never overwrites."""
    title = str(packet.get("title") or "").strip()
    if title != APPROVED_TITLE:
        raise WechatDraftSafetyError("packet title is not the approved stockout title")
    cta_url = str((packet.get("cta") or {}).get("url") or "")
    cta_copy = str((packet.get("cta") or {}).get("copy") or "")
    digest = str(packet.get("digest") or packet.get("excerpt") or "")
    markdown = str(packet.get("body_markdown") or "")
    if packet.get("image_status") != "images_ready":
        raise WechatDraftSafetyError("packet images are not ready")

    image_paths = verify_local_images(packet, root)
    listed = prelisted if prelisted is not None else list_all_drafts(client)
    pre_titles = collect_titles(listed)
    unrelated_ok = preserved_unrelated_present(pre_titles)
    duplicate = find_exact_title_item(listed, title)

    result: dict[str, Any] = {
        "piece_id": PIECE_ID,
        "ops_date": PHASE1_DATE,
        "mode": "draft_only",
        "status": "blocked_exact_title_duplicate" if duplicate else STATUS_CREATED,
        "title": title,
        "author": AUTHOR,
        "cta_url": cta_url,
        "safety": {
            "delete": False,
            "overwrite": False,
            "publish": False,
            "mass_send": False,
            "llm_api": False,
            "image_generation": False,
        },
        "pre_create": {
            "total_count": listed.get("total_count"),
            "item_count": listed.get("item_count"),
            "titles": pre_titles,
        },
        "preserved_unrelated": {
            "title": PRESERVED_UNRELATED_TITLE,
            "present_before": unrelated_ok,
        },
        "exact_title_duplicate": bool(duplicate),
        "created": False,
    }

    if duplicate:
        media_id = str(duplicate.get("media_id") or "")
        stored = client.get_draft(media_id)
        stored_article = (stored.get("news_item") or [{}])[0]
        expected = {
            "title": title,
            "author": AUTHOR,
            "digest": truncate_utf8(digest),
            "content_source_url": cta_url,
            "thumb_media_id": stored_article.get("thumb_media_id") or "",
        }
        readback = verify_readback(
            stored,
            expected,
            illustration_url="",
            require_uploaded_thumb=False,
        )
        result.update(
            {
                "status": STATUS_CREATED,
                "created": False,
                "media_id": media_id,
                "digest": stored_article.get("digest") or truncate_utf8(digest),
                "content_source_url": stored_article.get("content_source_url") or cta_url,
                "thumb_media_id_present": bool(stored_article.get("thumb_media_id")),
                "html": stored_article.get("content") or "",
                "readback": readback,
                "post_create": result["pre_create"],
                "preserved_unrelated": {
                    "title": PRESERVED_UNRELATED_TITLE,
                    "present_before": unrelated_ok,
                    "present_after": unrelated_ok,
                },
                "message": (
                    "Exact title already exists; skipped draft/add to avoid duplicate. "
                    "Existing draft was read back and verified without overwrite."
                ),
            }
        )
        return result

    thumb = client.upload_permanent_image(str(image_paths["cover"]))
    thumb_media_id = str(thumb.get("media_id") or "")
    illustration_url = upload_body_image(client, str(image_paths["illustration"]))
    html = build_stockout_html(
        markdown,
        illustration_url=illustration_url,
        cta_url=cta_url,
        cta_copy=cta_copy,
    )
    article = build_article_payload(
        title=title,
        html=html,
        thumb_media_id=thumb_media_id,
        digest=digest,
        content_source_url=cta_url,
        author=AUTHOR,
    )
    media_id = client.create_draft([article])
    stored = client.get_draft(media_id)
    readback = verify_readback(stored, article, illustration_url=illustration_url)
    post = list_all_drafts(client)
    post_titles = collect_titles(post)
    created_item = find_exact_title_item(post, title)

    result.update(
        {
            "status": STATUS_CREATED,
            "created": True,
            "media_id": media_id,
            "digest": article["digest"],
            "content_source_url": article["content_source_url"],
            "thumb_media_id_present": bool(thumb_media_id),
            "html": html,
            "cover": {
                "asset_path": str(image_paths["cover"].relative_to(root)),
                "sha256": sha256_file(image_paths["cover"]),
            },
            "illustration": {
                "asset_path": str(image_paths["illustration"].relative_to(root)),
                "sha256": sha256_file(image_paths["illustration"]),
                "cdn_host": "mmbiz.qpic.cn" if "mmbiz.qpic.cn" in illustration_url else "",
            },
            "readback": readback,
            "post_create": {
                "total_count": post.get("total_count"),
                "item_count": post.get("item_count"),
                "titles": post_titles,
            },
            "preserved_unrelated": {
                "title": PRESERVED_UNRELATED_TITLE,
                "present_before": unrelated_ok,
                "present_after": preserved_unrelated_present(post_titles),
                "media_id": next(
                    (
                        str(item.get("media_id") or "")
                        for item in (post.get("item") or [])
                        if PRESERVED_UNRELATED_TITLE
                        in [
                            str(n.get("title") or "")
                            for n in (item.get("content") or {}).get("news_item") or []
                        ]
                    ),
                    "",
                ),
            },
            "created_item_present": bool(created_item),
            "message": "Draft created and verified via draft/add + draft/get.",
        }
    )
    if unrelated_ok and not result["preserved_unrelated"]["present_after"]:
        raise WechatDraftSafetyError(
            "Unrelated single-point-contribution draft disappeared after create"
        )
    return result


def evidence_public_view(result: dict[str, Any]) -> dict[str, Any]:
    """Evidence JSON without full HTML body (kept as a sibling file)."""
    payload = {
        key: value
        for key, value in result.items()
        if key != "html"
    }
    payload["verified_at"] = utc_now_iso()
    payload["evidence_html"] = (
        f"data/growth/evidence/{PHASE1_DATE}/{PIECE_ID}/article.html"
    )
    if payload.get("media_id"):
        mid = str(payload["media_id"])
        payload["media_id_prefix"] = (mid[:10] + "…") if len(mid) > 10 else mid
    return payload


def apply_wechat_draft_created(
    manifest: dict[str, Any],
    packet: dict[str, Any],
    *,
    result: dict[str, Any],
    inspection: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Patch committed manifest/packet; preserve unrelated Zhihu publication fields."""
    updated_manifest = json.loads(json.dumps(manifest))
    updated_packet = json.loads(json.dumps(packet))
    updated_manifest["status"] = STATUS_CREATED
    updated_manifest["safety"] = result.get("safety") or updated_manifest.get("safety")
    updated_manifest["wechat_draft_inspection"] = {
        "total_count": inspection.get("total_count"),
        "item_count": inspection.get("item_count"),
        "overlap_count": len(inspection.get("plan_overlap") or []),
        "five_metrics_wechat_draft_present": bool(
            (updated_manifest.get("wechat_draft_inspection") or {}).get(
                "five_metrics_wechat_draft_present"
            )
        )
        or any(
            o.get("piece_id") == "w1-wechat-five-metrics"
            for o in inspection.get("plan_overlap") or []
        ),
        "stockout_draft_present": any(
            o.get("piece_id") == PIECE_ID for o in inspection.get("plan_overlap") or []
        ),
        "report_json": "data/growth/wechat-draft-inspection-2026-08-15.json",
        "report_md": "docs/reports/wechat-draft-inspection-2026-08-15.md",
    }
    updated_manifest["wechat_draft"] = {
        "piece_id": PIECE_ID,
        "status": result.get("status"),
        "title": result.get("title"),
        "media_id": result.get("media_id"),
        "created": result.get("created"),
        "exact_title_duplicate": result.get("exact_title_duplicate"),
        "evidence": f"data/growth/evidence/{PHASE1_DATE}/{PIECE_ID}/verification.json",
    }
    for item in updated_manifest.get("packets") or []:
        if item.get("piece_id") == PIECE_ID:
            item["status"] = result.get("status")
            item["draft_media_id"] = result.get("media_id")
            item["evidence"] = {
                "verification_json": (
                    f"data/growth/evidence/{PHASE1_DATE}/{PIECE_ID}/verification.json"
                ),
                "article_html": f"data/growth/evidence/{PHASE1_DATE}/{PIECE_ID}/article.html",
            }
    updated_manifest["generated_at"] = utc_now_iso()

    updated_packet["status"] = result.get("status")
    updated_packet["action"] = "wechat_draft_created"
    updated_packet["draft"] = {
        "media_id": result.get("media_id"),
        "author": result.get("author"),
        "digest": result.get("digest"),
        "content_source_url": result.get("content_source_url"),
        "created": result.get("created"),
        "verified_at": utc_now_iso(),
    }
    return updated_manifest, updated_packet


def load_wechat_env(env_path: Path | None = None) -> tuple[str, str]:
    """Load WECHAT_APPID / WECHAT_SECRET only. Never returns or prints other keys."""
    root = Path(__file__).resolve().parents[1]
    app_id = os.environ.get("WECHAT_APPID", "").strip()
    secret = os.environ.get("WECHAT_SECRET", "").strip()
    if app_id and secret:
        return app_id, secret
    candidates = [
        env_path,
        root / ".env",
        Path(
            "/Users/Logan/AICoding/ZeroRealmAI/ZeroRealmAI-migrate-manual-20260812/"
            "secrets/zerorealm-data.env"
        ),
    ]
    for path in candidates:
        if path is None or not path.is_file():
            continue
        local_id = ""
        local_secret = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "WECHAT_APPID" and value and "your-appid" not in value.lower():
                local_id = value
            elif key == "WECHAT_SECRET" and value and "your-secret" not in value.lower():
                local_secret = value
        if local_id and local_secret:
            return local_id, local_secret
    raise WechatDraftSafetyError(
        "WECHAT_APPID/WECHAT_SECRET not found in environment or known secret files."
    )
