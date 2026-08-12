"""Upload smart-cabinet five-metrics article to WeChat draft box only (no mass send)."""

from __future__ import annotations

import json
import os
import re
import sys
from html import escape
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from publishing.wechat.client import WechatClient  # noqa: E402

PKG = ROOT / "dist/content-package/smart-cabinet-five-process-metrics"


def md_to_wechat_html(md: str, info_url: str) -> str:
    lines = md.splitlines()
    i = 0
    if lines and lines[0].startswith("# "):
        i = 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].startswith(">"):
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1
    if i < len(lines) and lines[i].startswith("![]("):
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1

    body = "\n".join(lines[i:])
    body = re.sub(
        r"\n---\n+!\[[^\]]*\]\(\.\./media/infographic\.png\)\s*$",
        "",
        body,
    )
    body = body.replace("![5个过程指标协同影响经营结果](../media/infographic.png)", "")
    body = body.replace("![](../media/cover.png)", "")

    parts: list[str] = []
    for block in re.split(r"\n\n+", body.strip()):
        b = block.strip()
        if not b or b == "---":
            continue
        if b.startswith("## "):
            title = escape(b[3:].strip())
            parts.append(
                '<h2 style="margin:28px 0 14px;font-size:20px;line-height:1.5;'
                f'color:#0f172a;font-weight:600;">{title}</h2>'
            )
            continue
        if b.startswith("- "):
            items: list[str] = []
            for line in b.splitlines():
                line = line.strip()
                if not line.startswith("- "):
                    continue
                item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[2:])
                items.append(f'<li style="margin:0 0 8px;">{item}</li>')
            parts.append(
                '<ul style="margin:0 0 16px;padding-left:1.2em;font-size:16px;'
                'line-height:1.85;color:#334155;">'
                + "".join(items)
                + "</ul>"
            )
            continue

        text = " ".join(x.strip() for x in b.splitlines() if x.strip())
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = (
            escape(text)
            .replace("&lt;strong&gt;", "<strong>")
            .replace("&lt;/strong&gt;", "</strong>")
        )
        if text.startswith("<strong>ZeroRealm 判断"):
            parts.append(
                '<p style="margin:0 0 16px;padding:12px 14px;background:#f8fafc;'
                'border-left:3px solid #5a7a8c;font-size:16px;line-height:1.85;'
                f'color:#1f2937;">{text}</p>'
            )
        else:
            parts.append(
                '<p style="margin:0 0 16px;font-size:16px;line-height:1.85;'
                f'color:#334155;">{text}</p>'
            )

    html = "\n".join(parts)
    info_html = (
        '<p style="margin:24px 0 8px;">'
        f'<img src="{escape(info_url, quote=True)}" alt="5个过程指标协同影响经营结果" '
        'style="display:block;width:100%;height:auto;" />'
        "</p>"
        '<p style="margin:0 0 20px;font-size:13px;color:#64748b;line-height:1.6;">'
        "图：5个过程指标协同影响经营结果（示意协同关系，非单向因果）"
        "</p>"
    )
    marker = (
        '<h2 style="margin:28px 0 14px;font-size:20px;line-height:1.5;'
        'color:#0f172a;font-weight:600;">结尾</h2>'
    )
    if marker in html:
        html = html.replace(marker, info_html + marker, 1)
    else:
        html += info_html
    return html


def truncate_utf8(text: str, limit: int = 120) -> str:
    raw = text.encode("utf-8")[:limit]
    while True:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raw = raw[:-1]


def main() -> int:
    app_id = os.getenv("WECHAT_APPID", "").strip()
    secret = os.getenv("WECHAT_SECRET", "").strip()
    configured = bool(
        app_id
        and secret
        and "your-appid" not in app_id
        and "your-secret" not in secret
    )
    if not configured:
        print(json.dumps({"uploaded": False, "reason": "wechat_credentials_missing"}, ensure_ascii=False))
        return 1

    draft_md = (PKG / "wechat" / "draft.md").read_text(encoding="utf-8")
    digest = (PKG / "wechat" / "digest.txt").read_text(encoding="utf-8").strip()
    meta = json.loads((PKG / "metadata.json").read_text(encoding="utf-8"))
    title = meta["title"]
    cover_path = PKG / "media" / "cover.png"
    info_path = PKG / "media" / "infographic.png"

    client = WechatClient(app_id, secret)
    token = client.get_access_token()
    cover_up = client.upload_permanent_image(str(cover_path))
    thumb = cover_up.get("media_id", "")
    info_url = client.upload_content_image(str(info_path))
    content = md_to_wechat_html(draft_md, info_url)

    payload = {
        "title": title,
        "author": "ZeroRealm AI",
        "digest": truncate_utf8(digest, 120),
        "content": content,
        "thumb_media_id": thumb,
        "need_open_comment": 1,
        "only_fans_can_comment": 1,
    }
    draft_id = client.create_draft([payload])
    stored = client.get_draft(draft_id)
    items = stored.get("news_item") or stored.get("item") or []
    ok = False
    if items:
        art = items[0]
        content_stored = art.get("content", "")
        ok = (
            art.get("title") == title
            and bool(content_stored)
            and "协同观察" in content_stored
            and "→" not in content_stored
        )

    out = {
        "uploaded": True,
        "draft_id": draft_id,
        "token_ok": bool(token),
        "thumb_ok": bool(thumb),
        "info_url_ok": str(info_url).startswith("http"),
        "readback_ok": ok,
        "publish_now": False,
        "mass_send": False,
        "status": "ready_for_manual_publish" if ok else "draft_uploaded_verify_failed",
    }
    (PKG / "wechat" / "upload_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    meta["wechat"]["status"] = out["status"]
    meta["wechat"]["draftId"] = draft_id
    meta["wechat"]["apiCalled"] = True
    meta["wechat"]["massSend"] = False
    meta["wechat"]["publishNow"] = False
    meta["media"]["coverReviewStatus"] = "approved"
    meta["media"]["infographicReviewStatus"] = "approved"
    (PKG / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
