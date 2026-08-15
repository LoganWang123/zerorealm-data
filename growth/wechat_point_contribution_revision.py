"""Production revision for WeChat draft《点位有销量却不赚钱？用一张周表算清单点贡献》.

Local packet + Agy browser sync writeback.
Draft sync may be marked completed; never marks scheduled/published/auto_publish.
Never records CDN URLs, file_id, login tokens, cookies, or asset addresses.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any

from growth.wechat_stockout_draft import (
    assert_html_visible_text_chinese_only,
    assert_no_latin_visible,
    latin_tokens,
    visible_text_from_html,
)

OPS_DATE = "2026-08-15"
PIECE_ID = "o1-wechat-point-contribution"
TITLE = "点位有销量却不赚钱？用一张周表算清单点贡献"
AUTHOR = "零域研究"
STATUS_PRODUCTION_READY_REVISION = "production_ready_revision"
STATUS_EXTERNAL_SYNC_PENDING = "external_sync_pending"
STATUS_EXTERNAL_SYNC_COMPLETED = "external_sync_completed"
STATUS_DRAFT_SAVED = "draft_saved"
FORBIDDEN_PUBLISH_STATUSES = frozenset(
    {
        "scheduled",
        "published",
        "timed",
        "已发布",
        "已定时",
    }
)
# Legacy alias: publish/schedule markers only (draft sync may set synced=true).
FORBIDDEN_SYNC_STATUSES = FORBIDDEN_PUBLISH_STATUSES

EXTERNAL_APP_ID = "100000152"
EXTERNAL_DATA_SEQ_PREVIOUS = "4649592826320846849"
EXTERNAL_DATA_SEQ = "4650782630374998016"
EXTERNAL_MEDIA_ID = "csbrZswCx_5hmuZ_bqWc6_aMLRMtgyHDcCnExyNx_zUuzOODWrtB0uYPC2pZYh1m"
AGY_MODEL = "gemini-3.7-flash-high"
AGY_ACCEPTANCE = "PASS"
AGY_VERIFIED_AT = "2026-08-15T21:28:37+08:00"
AGY_VIA = "browser_manual"

CTA_EXACT = "回复「复盘表」打开周经营复盘工具"
CORE_QUESTION = "点位流水不等于赚钱，先用周表算清单点贡献再决定调优或暂时撤点"
CORE_QUESTION_TAGS = frozenset(
    {
        "单点贡献",
        "点位赚钱",
        "点位流水",
        "周表",
        "撤点",
        "调优",
        "点位贡献",
    }
)

DIGEST = (
    "点位有流水，不等于点位赚钱。公开材料无法核实全行业均值，"
    "但友宝、日本大同饮料和富士电机的公开披露支持一个假设："
    "先用自己的周表算清单点贡献，再决定调优或暂时撤点。"
)

PROFESSIONAL_BOUNDARY_ZH = (
    "本文仅基于公开披露、合成示例与通用运营场景；"
    "不使用现任公司内部数据、客户名单、未公开案例或同事观点，也不以雇主名义发言。"
)

SAME_CHANNEL_TOPIC_WINDOW_DAYS = 14
CANCEL_REASON_TOPIC_OVERLAP = "same_channel_topic_overlap_with_2026-08-15_article"

FORBIDDEN_VISIBLE_TERMS = (
    "DyDo",
    "Fuji Electric",
    "Fuji",
    "ZeroRealm AI",
    "ZeroRealm",
    "SKU",
    "GMV",
    "IR",
    "Excel",
    "excel",
    "hi@zerorealm.tech",
    "zerorealm.tech",
    "下载表格",
    "下载模板",
    "单点贡献表文件",
    "预约运营商访谈",
    "加微信",
    "一对一",
    "私聊",
    "人工跟进",
    "留下公司",
    "点位地址",
    "点位身份",
)

LATIN_TOKEN_RE = re.compile(r"[A-Za-z]+")
RAW_URL_RE = re.compile(r"https?://", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def body_markdown() -> str:
    return f"""# {TITLE}

> 口径：公开披露与零域研究参考字段；非行业均值、非会计准则、无收益承诺。
> {PROFESSIONAL_BOUNDARY_ZH}

点位有流水，不等于点位赚钱。公开材料里没有「中国智能柜行业平均单点贡献」，也核实不到「全行业已完成从规模到质量转型」。能核对的是三组发行人信号——友宝、日本大同饮料、富士电机——它们只支持一个运营假设：先用自己的周表算清单点贡献，再决定调优或暂时撤点。

## 三个信号，支撑运营假设

### 友宝｜港交所披露

事实机制｜2025年无人零售营收同比降6.5%，公司归因于淘汰低毛利点位并开发高毛利点位；同期无人零售毛利率升至49.5%，并写明继续优化点位网络、提高智能设备占比，目标改善毛利率与单点利润。

运营含义｜点位质量可优先于点位数量，但发行人汇总数字不能直接当成你的单点贡献。

### 日本大同饮料｜官方投资者关系披露

事实机制｜国内饮料事业2025财年分部利润率-1.6%；公司披露于第4季度计提减损损失29,826百万日元，并强化从不盈利自贩机点位撤出、转向收益导向。

运营含义｜若分部层面已亏，规模扩张更要回到点位收益筛选；迁移到中国智能柜时须保留场景边界。

### 富士电机｜官方投资者关系披露

事实机制｜影响营业利润的因素包括人员成本上升与物流费用高企；管理层优先事项包括自动售货机运营精简与配送路线效率。

运营含义｜履约与线路成本会吃掉点位贡献，值得在自建周表里单独记账；同样不是行业通论。

三组都是公司特定披露，不是行业均值。更稳妥的读法是，当运营方开始淘汰低贡献点位、计提减值或主动压缩履约成本时，单点质量问题已被推到台前——这支持运营者自建周贡献核算的假设。

## 零域研究参考周表（甲至己）

「零域研究参考周核算板」不是行业标准，不是会计准则，也不是发行人报表科目的一一映射；用途是帮运营用自己的基线做可逆对照。按点位、按自然周记录六行。

- 甲　点位销售收入
- 乙　商品成本
- 丙　场地租金或分成
- 丁　补货或线路履约成本
- 戊　支付、平台或其他变动经营成本
- 己　损耗、退款或异常损失

**周单点贡献 = 甲 − 乙 − 丙 − 丁 − 戊 − 己**

默认口径落在设备折旧与总部固定费用之前。若你选择分摊折旧或总部费用，请单独加行并注明，不要与周贡献混为一谈。友宝费用行与日本大同饮料分部损益不能直接填进甲至己，因为公开披露通常缺少单点拆分。

## 每周流程与两周可逆实验

每周固定五步。

1. 用同一口径连续记录，建立自己的基线。
2. 找出周贡献为负或相对自身基线明显走弱的点位。
3. 诊断最大成本行（看乙至己哪一行在吃掉贡献）。
4. 只选一个可逆动作——单品精简、补货频次调整、线路聚类、商务条款重谈、或临时撤点或暂停。
5. 两周后对照贡献与服务质量（缺货、客诉等）。

判断标准只来自你自己的基线前后差，以及你可接受的服务底线；不要套用外部「及格线」或统一阈值。若贡献未改善且服务变差，回滚动作。本文不承诺任何收益结果。

## 证据边界

文中数字分别来自友宝港交所、日本大同饮料官方投资者关系披露与富士电机官方投资者关系披露，均为公司特定口径，不是中国智能柜行业平均贡献，也不证明全行业已转型。日本大同饮料与富士电机是相邻自动售货或设备一手证据，迁移到中国智能柜场景必须保留边界。现有公开材料未披露单点收入成本拆分，因此无法用发行人汇总数字直接算出单点贡献。友宝毛利率提升可能受商品批发与广告业务协同影响；日本大同饮料亏损口径可能包含减值等项目。甲至己周核算板为零域研究参考字段，默认在折旧与总部固定费用之前，供运营用自有基线做可逆实验，不是标准公式。

{PROFESSIONAL_BOUNDARY_ZH}

## 唯一行动入口

{CTA_EXACT}
"""


def build_revision_html(*, body_md: str | None = None) -> str:
    """WeChat-ready HTML: Chinese-only visible text; no raw URL/email; exact CTA."""
    md = body_md if body_md is not None else body_markdown()
    lines = md.replace("\r\n", "\n").strip().split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("# ") and not stripped.startswith("## "):
            i += 1
            continue
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            blocks.append(
                '<section style="margin:28px 0 14px;padding-left:12px;'
                'border-left:4px solid #387896;">'
                f'<h2 style="margin:0;font-size:20px;line-height:1.5;color:#0f172a;">'
                f"{escape(heading)}</h2></section>"
            )
            if heading == "唯一行动入口":
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("#"):
                    nxt = lines[i].strip()
                    if nxt and nxt != CTA_EXACT:
                        raise ValueError(f"CTA section must only contain exact CTA, got: {nxt}")
                    i += 1
                blocks.append(
                    '<div style="margin:22px 0;padding:18px;background:#eff6ff;'
                    'border:1px solid #bfdbfe;border-radius:8px;">'
                    '<p style="margin:0;font-size:16px;line-height:1.8;font-weight:600;'
                    f'color:#0f172a;text-align:center;">{escape(CTA_EXACT)}</p></div>'
                )
                continue
            i += 1
            continue
        if stripped.startswith("### "):
            blocks.append(
                f'<h3 style="margin:20px 0 10px;font-size:17px;line-height:1.6;color:#0f172a;">'
                f"{escape(stripped[4:].strip())}</h3>"
            )
            i += 1
            continue
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            inner = "<br/>".join(escape(x) for x in quote_lines)
            blocks.append(
                '<blockquote style="margin:0 0 20px;padding:12px 14px;background:#f8fafc;'
                'border-left:4px solid #387896;color:#475569;font-size:14px;line-height:1.8;">'
                f"{inner}</blockquote>"
            )
            continue
        if stripped.startswith("- "):
            items: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            lis = "".join(
                '<li style="margin:0 0 8px;font-size:16px;line-height:1.7;color:#334155;">'
                f"{_inline_md(item)}</li>"
                for item in items
            )
            blocks.append(
                f'<ul style="margin:0 0 14px;padding-left:22px;list-style:disc;">{lis}</ul>'
            )
            continue
        if re.match(r"\d+\. ", stripped):
            items = []
            while i < len(lines) and re.match(r"\d+\. ", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s*", "", lines[i].strip()))
                i += 1
            lis = "".join(
                '<li style="margin:0 0 8px;font-size:16px;line-height:1.75;color:#334155;">'
                f"{_inline_md(item)}</li>"
                for item in items
            )
            blocks.append(
                f'<ol style="margin:0 0 16px;padding-left:22px;list-style:decimal;">{lis}</ol>'
            )
            continue
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith("#")
                or nxt.startswith(">")
                or nxt.startswith("- ")
                or re.match(r"\d+\. ", nxt)
            ):
                break
            para_lines.append(nxt)
            i += 1
        text = " ".join(para_lines)
        if text.startswith("**") and text.endswith("**"):
            blocks.append(
                '<p style="margin:0 0 16px;padding:12px 14px;background:#0f172a;color:#f8fafc;'
                'border-radius:8px;font-size:16px;line-height:1.7;font-weight:700;">'
                f"{escape(text[2:-2])}</p>"
            )
        else:
            blocks.append(
                '<p style="margin:0 0 16px;font-size:16px;line-height:1.9;color:#334155;">'
                f"{_inline_md(text)}</p>"
            )

    html = (
        '<div style="max-width:100%;padding:8px 4px;'
        'font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",'
        "sans-serif;\">"
        + "".join(blocks)
        + "</div>"
    )
    assert_revision_visible_chinese_only(html=html, title=TITLE, author=AUTHOR, digest=DIGEST)
    assert_exact_cta_only(html)
    return html


def _inline_md(text: str) -> str:
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            out.append(f"<strong>{escape(part[2:-2])}</strong>")
        else:
            out.append(escape(part))
    return "".join(out)


def assert_exact_cta_only(html: str) -> None:
    visible = visible_text_from_html(html)
    if CTA_EXACT not in visible:
        raise ValueError("visible HTML must include exact CTA")
    if visible.count(CTA_EXACT) != 1:
        raise ValueError("exact CTA must appear exactly once")
    for term in (
        "打开智能柜周复盘工具页",
        "下载",
        "Excel",
        "表格文件",
        "模板",
        "访谈",
        "加微信",
        "一对一",
        "私聊",
        "人工跟进",
    ):
        if term.lower() in visible.lower() and term not in CTA_EXACT:
            # 「复盘表」 is inside CTA; allow. Block download/interview terms.
            if term in {"下载", "Excel", "表格文件", "模板", "访谈", "加微信", "一对一", "私聊", "人工跟进"}:
                raise ValueError(f"forbidden CTA/outreach term in visible text: {term}")


def assert_revision_visible_chinese_only(
    *,
    html: str,
    title: str,
    author: str,
    digest: str,
) -> None:
    assert_no_latin_visible(title, field="title")
    assert_no_latin_visible(author, field="author")
    assert_no_latin_visible(digest, field="digest")
    assert_html_visible_text_chinese_only(html)
    visible = visible_text_from_html(html)
    if RAW_URL_RE.search(visible) or EMAIL_RE.search(visible):
        raise ValueError("visible text must not show raw URL or email")
    for term in FORBIDDEN_VISIBLE_TERMS:
        if term in visible or term in digest or term in title or term in author:
            raise ValueError(f"forbidden visible term present: {term}")
    # Digits and Chinese punctuation only — no Latin formula letters.
    if re.search(r"[A-Fa-f]\s*[−\-]\s*[A-Fa-f]", visible):
        raise ValueError("Latin formula variables must be replaced with 甲至己")


def privacy_guard_block() -> dict[str, bool]:
    """Acceptance writeback must never record secrets or asset addresses."""
    return {
        "cdn_urls_recorded": False,
        "file_ids_recorded": False,
        "login_tokens_recorded": False,
        "cookies_recorded": False,
        "asset_addresses_recorded": False,
    }


def agy_acceptance_block() -> dict[str, Any]:
    return {
        "model": AGY_MODEL,
        "result": AGY_ACCEPTANCE,
        "verified_at": AGY_VERIFIED_AT,
        "via": AGY_VIA,
        "app_id": EXTERNAL_APP_ID,
        "data_seq": EXTERNAL_DATA_SEQ,
        "data_seq_previous": EXTERNAL_DATA_SEQ_PREVIOUS,
        "platform_state": "draft",
        "author": AUTHOR,
        "digest_complete": True,
        "body_chinese_only": True,
        "body_image_count": 3,
        "cover_variants_retained": 2,
        "cta_exact": CTA_EXACT,
        "latin_visible_count": 0,
        "raw_url_count": 0,
        "email_count": 0,
        "forbidden_term_count": 0,
        "no_download_promise": True,
        "professional_boundary_pass": True,
        "scheduled": False,
        "published": False,
        "auto_publish": False,
        "privacy": privacy_guard_block(),
    }


def assert_not_marked_synced_or_published(payload: dict[str, Any]) -> None:
    """Backward-compatible name: draft sync may be true; publish/schedule must not."""
    assert_draft_synced_not_published(payload)


def assert_draft_synced_not_published(payload: dict[str, Any]) -> None:
    """Draft external sync ≠ scheduled/published/auto_publish."""
    blob = json.dumps(payload, ensure_ascii=False)
    for bad in ("已发布", "已定时"):
        if f'"{bad}"' in blob or f"：{bad}" in blob or f": {bad}" in blob:
            raise ValueError(f"must not mark status as {bad}")
    status = payload.get("status")
    sync = payload.get("external_sync_status")
    draft_status = payload.get("draft_status")
    if status in FORBIDDEN_PUBLISH_STATUSES or sync in FORBIDDEN_PUBLISH_STATUSES:
        raise ValueError("must not mark point-contribution as scheduled/published")
    if status != STATUS_PRODUCTION_READY_REVISION:
        raise ValueError("status must remain production_ready_revision")
    if sync != STATUS_EXTERNAL_SYNC_COMPLETED:
        raise ValueError("external_sync_status must be external_sync_completed")
    if draft_status != STATUS_DRAFT_SAVED:
        raise ValueError("draft_status must be draft_saved")
    if payload.get("scheduled") or payload.get("published"):
        raise ValueError("scheduled/published flags must be false")
    if payload.get("auto_publish") is True:
        raise ValueError("auto_publish must be false")
    compliance = payload.get("compliance") or {}
    if compliance.get("auto_publish") is True:
        raise ValueError("compliance.auto_publish must be false")
    if payload.get("synced") is not True:
        raise ValueError("synced must be true after Agy draft acceptance")
    privacy = (
        payload.get("privacy")
        or (payload.get("agy_acceptance") or {}).get("privacy")
        or {}
    )
    for key, expected in privacy_guard_block().items():
        if key in privacy and privacy[key] is not expected:
            raise ValueError(f"privacy.{key} must be {expected}")
    assert_no_privacy_secrets_in_blob(payload)


def assert_no_privacy_secrets_in_blob(payload: dict[str, Any]) -> None:
    blob = json.dumps(payload, ensure_ascii=False)
    if "mmbiz.qpic.cn" in blob or "Set-Cookie" in blob:
        raise ValueError("must not record CDN/cookie material")
    if re.search(r'"file_id"\s*:\s*"[^"]+"', blob):
        raise ValueError("must not record file_id values")
    if re.search(r'"login_token"\s*:\s*"[^"]+"', blob):
        raise ValueError("must not record login_token values")
    if re.search(r'"(cookie|cookies)"\s*:\s*"[^"]+"', blob, re.IGNORECASE):
        raise ValueError("must not record cookie values")
    if re.search(r'"asset_(url|address)"\s*:\s*"[^"]+"', blob):
        raise ValueError("must not record asset addresses")


def normalize_core_question_text(text: str) -> set[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fff0-9]", " ", text or "")
    tokens = {t for t in cleaned.split() if len(t) >= 2}
    return tokens


def core_question_overlap_ratio(a: str, b: str) -> float:
    ta, tb = normalize_core_question_text(a), normalize_core_question_text(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def same_channel_core_question_blocked(
    *,
    channel: str,
    candidate_core_question: str,
    candidate_tags: set[str] | frozenset[str],
    existing: list[dict[str, Any]],
    candidate_date: str,
    window_days: int = SAME_CHANNEL_TOPIC_WINDOW_DAYS,
    overlap_threshold: float = 0.45,
) -> dict[str, Any] | None:
    """Return blocking record if another same-channel piece overlaps within window."""
    cand_day = date.fromisoformat(candidate_date)
    for row in existing:
        if row.get("channel") != channel:
            continue
        if row.get("scheduled") is False and row.get("published") is False:
            # Still count drafts/published plans that are not canceled.
            pass
        if row.get("status") == "canceled":
            continue
        other_day = date.fromisoformat(str(row["date"]))
        if abs((cand_day - other_day).days) > window_days:
            continue
        other_q = str(row.get("core_question") or row.get("title") or "")
        other_tags = set(row.get("core_question_tags") or [])
        tag_hit = bool(candidate_tags & other_tags)
        ratio = core_question_overlap_ratio(candidate_core_question, other_q)
        if tag_hit or ratio >= overlap_threshold:
            return {
                "blocked": True,
                "reason": CANCEL_REASON_TOPIC_OVERLAP
                if "2026-08-15" in (row.get("date") or candidate_date)
                else "same_channel_core_question_overlap_within_14d",
                "overlap_ratio": round(ratio, 4),
                "tag_intersection": sorted(candidate_tags & other_tags),
                "other_piece_id": row.get("piece_id"),
                "other_date": row.get("date"),
                "other_title": row.get("title"),
                "window_days": window_days,
            }
    return None


def assert_no_same_channel_core_question_overlap(
    *,
    channel: str,
    candidate_core_question: str,
    candidate_tags: set[str] | frozenset[str],
    existing: list[dict[str, Any]],
    candidate_date: str,
    window_days: int = SAME_CHANNEL_TOPIC_WINDOW_DAYS,
) -> None:
    hit = same_channel_core_question_blocked(
        channel=channel,
        candidate_core_question=candidate_core_question,
        candidate_tags=candidate_tags,
        existing=existing,
        candidate_date=candidate_date,
        window_days=window_days,
    )
    if hit:
        raise ValueError(
            "same-channel core-question overlap within "
            f"{window_days}d: {hit['other_piece_id']} on {hit['other_date']}"
        )


def build_revision_packet(*, body_md: str | None = None) -> dict[str, Any]:
    md = body_md if body_md is not None else body_markdown()
    html = build_revision_html(body_md=md)
    acceptance = agy_acceptance_block()
    packet = {
        "schema_version": 1,
        "ops_date": OPS_DATE,
        "piece_id": PIECE_ID,
        "channel": "wechat",
        "format": "article",
        "action": STATUS_PRODUCTION_READY_REVISION,
        "status": STATUS_PRODUCTION_READY_REVISION,
        "external_sync_status": STATUS_EXTERNAL_SYNC_COMPLETED,
        "draft_status": STATUS_DRAFT_SAVED,
        "scheduled": False,
        "published": False,
        "synced": True,
        "auto_publish": False,
        "title": TITLE,
        "author": AUTHOR,
        "excerpt": DIGEST,
        "digest": DIGEST,
        "core_question": CORE_QUESTION,
        "core_question_tags": sorted(CORE_QUESTION_TAGS),
        "cta": {
            "copy": CTA_EXACT,
            "exact": True,
            "max_per_piece": 1,
            "no_excel_download_claim": True,
            "no_template_file_claim": True,
            "no_interview_or_one_to_one": True,
            "keyword_reply_only": True,
            "keyword": "复盘表",
        },
        "external_draft": {
            "app_id": EXTERNAL_APP_ID,
            "data_seq": EXTERNAL_DATA_SEQ,
            "data_seq_previous": EXTERNAL_DATA_SEQ_PREVIOUS,
            "media_id": EXTERNAL_MEDIA_ID,
            "account": "ZeroRealm零域AI",
            "platform_state": "draft",
            "updated_at": AGY_VERIFIED_AT,
            "note": (
                "Agy（gemini-3.7-flash-high）已浏览器同步并验收 PASS："
                "草稿已保存；synced=true；scheduled=false；published=false；"
                "auto_publish=false。草稿同步≠发布。"
            ),
        },
        "agy_acceptance": acceptance,
        "privacy": privacy_guard_block(),
        "visible_fields_for_agy": {
            "title": "title",
            "author": "author",
            "digest": "digest",
            "body_html": "body_html",
            "cta": "cta.copy",
            "keep_existing_images": True,
            "do_not_delete_external_draft": True,
        },
        "body_markdown": md,
        "body_html": html,
        "compliance": {
            "wechat_visible_text_chinese_only": True,
            "no_raw_visible_urls": True,
            "no_visible_email": True,
            "no_latin_brand_or_acronym": True,
            "no_excel_or_template_download_claim": True,
            "no_interview_cta": True,
            "no_one_to_one_contact_ask": True,
            "no_wechat_add_ask": True,
            "no_company_or_site_identity_ask": True,
            "no_industry_average_claim": True,
            "no_accounting_standard_claim": True,
            "no_revenue_promise": True,
            "two_week_reversible_experiment": True,
            "public_disclosure_evidence_boundary": True,
            "professional_boundaries_zh": PROFESSIONAL_BOUNDARY_ZH,
            "conversion_funnel": "公开内容 → 关注公众号 → 回复「复盘表」→ 自助使用周经营复盘工具",
            "auto_publish": False,
            "llm_api_used": False,
            "external_state_mutated": False,
        },
        "anti_duplication": {
            "channel": "wechat",
            "window_days": SAME_CHANNEL_TOPIC_WINDOW_DAYS,
            "rule": (
                "同一公众号十四天内，核心问题高度相似的内容禁止再发布；"
                f"冲突时保留更早稿，取消后续计划并标注 {CANCEL_REASON_TOPIC_OVERLAP}。"
            ),
            "cancel_reason_code": CANCEL_REASON_TOPIC_OVERLAP,
        },
        "prepared_at": utc_now_iso(),
        "owner_github": "LoganWang123",
    }
    assert_draft_synced_not_published(packet)
    assert_revision_visible_chinese_only(
        html=html, title=TITLE, author=AUTHOR, digest=DIGEST
    )
    return packet


def render_agy_handoff_markdown(packet: dict[str, Any]) -> str:
    ext = packet["external_draft"]
    acceptance = packet.get("agy_acceptance") or agy_acceptance_block()
    return "\n".join(
        [
            f"# Agy 浏览器同步稿 · {TITLE}",
            "",
            "## 状态（已回写）",
            "",
            f"- local status: `{packet['status']}`",
            f"- external_sync_status: `{packet['external_sync_status']}`",
            f"- draft_status: `{packet.get('draft_status', STATUS_DRAFT_SAVED)}`",
            "- synced: **true**（草稿同步完成）",
            "- scheduled / published / auto_publish: **false**",
            "- 草稿同步 ≠ 发布；禁止操作公众号后台自动发表或群发。",
            "",
            "## Agy 验收",
            "",
            f"- model: `{acceptance['model']}`",
            f"- result: `{acceptance['result']}`",
            f"- verified_at: `{acceptance['verified_at']}`",
            f"- via: `{acceptance['via']}`",
            "",
            "## 外部草稿标识",
            "",
            f"- app_id: `{ext['app_id']}`",
            f"- data_seq: `{ext['data_seq']}`（previous: `{ext.get('data_seq_previous', EXTERNAL_DATA_SEQ_PREVIOUS)}`）",
            f"- platform_state: `{ext.get('platform_state', 'draft')}`",
            f"- updated_at: `{ext.get('updated_at', AGY_VERIFIED_AT)}`",
            "- 不记录 CDN URL / file_id / 登录令牌 / cookie / 素材地址",
            "",
            "## 可见字段位置",
            "",
            "- 标题 → packet.`title`",
            "- 作者 → packet.`author`（零域研究）",
            "- 摘要 → packet.`digest`",
            "- 正文 → packet.`body_html`（保留草稿内既有配图，勿删图）",
            "- 唯一 CTA → packet.`cta.copy`："
            f"`{CTA_EXACT}`",
            "",
            "## 摘要（完整，不截断）",
            "",
            DIGEST,
            "",
            "## 职业边界（文内短句，非长免责）",
            "",
            PROFESSIONAL_BOUNDARY_ZH,
            "",
            "## 同步检查（Agy PASS）",
            "",
            "- [x] 可见正文无拉丁字母品牌/缩写/公式变量",
            "- [x] 无可见原始网址、邮箱、英文署名或英文营销语",
            "- [x] 唯一 CTA 仅为回复「复盘表」打开周经营复盘工具",
            "- [x] 未承诺下载表格/模板/单点贡献表文件",
            "- [x] 未索取访谈、加微信、私聊、一对一或公司/点位身份",
            "- [x] 3 张正文图、2 种封面保留；platform_state=draft",
            "",
        ]
    )


def write_revision_artifacts(root: Path) -> dict[str, Path]:
    packet = build_revision_packet()
    # Preserve canonical contract fields if already present on disk.
    packet_path = root / f"data/growth/content-packet-{PIECE_ID}-{OPS_DATE}.json"
    if packet_path.is_file():
        existing = json.loads(packet_path.read_text(encoding="utf-8"))
        for key in ("canonical_id", "canonical_version", "contract", "prepared_at"):
            if key in existing and key not in ("prepared_at",):
                packet[key] = existing[key]
            elif key == "prepared_at" and "prepared_at" in existing:
                packet["prepared_at"] = existing["prepared_at"]
    paths = {
        "packet": packet_path,
        "markdown": root / f"content/organic_packets/{OPS_DATE}/{PIECE_ID}.md",
        "html": root
        / f"data/growth/evidence/{OPS_DATE}/{PIECE_ID}/article.html",
        "agy_handoff": root
        / f"docs/reports/wechat-point-contribution-revision-{OPS_DATE}.md",
        "agy_json": root
        / f"data/growth/agy-sync-{PIECE_ID}-{OPS_DATE}.json",
    }
    paths["markdown"].parent.mkdir(parents=True, exist_ok=True)
    paths["html"].parent.mkdir(parents=True, exist_ok=True)
    paths["agy_handoff"].parent.mkdir(parents=True, exist_ok=True)
    paths["packet"].parent.mkdir(parents=True, exist_ok=True)

    paths["markdown"].write_text(packet["body_markdown"] + "\n", encoding="utf-8")
    paths["html"].write_text(packet["body_html"] + "\n", encoding="utf-8")
    paths["packet"].write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths["agy_handoff"].write_text(
        render_agy_handoff_markdown(packet) + "\n", encoding="utf-8"
    )
    agy_payload = {
        "purpose": "agy_browser_sync_only",
        "status": packet["status"],
        "external_sync_status": packet["external_sync_status"],
        "draft_status": packet["draft_status"],
        "scheduled": False,
        "published": False,
        "synced": True,
        "auto_publish": False,
        "external_draft": {
            "app_id": packet["external_draft"]["app_id"],
            "data_seq": packet["external_draft"]["data_seq"],
            "data_seq_previous": packet["external_draft"]["data_seq_previous"],
            "account": packet["external_draft"]["account"],
            "platform_state": "draft",
            "updated_at": packet["external_draft"]["updated_at"],
            "note": packet["external_draft"]["note"],
        },
        "agy_acceptance": packet["agy_acceptance"],
        "privacy": packet["privacy"],
        "visible": {
            "title": packet["title"],
            "author": packet["author"],
            "digest": packet["digest"],
            "body_html": packet["body_html"],
            "cta": packet["cta"]["copy"],
        },
        "field_map": packet["visible_fields_for_agy"],
        "keep_existing_images": True,
        "do_not_operate_wechat_backend_publish": True,
    }
    assert_draft_synced_not_published(agy_payload)
    assert_no_privacy_secrets_in_blob(agy_payload)
    paths["agy_json"].write_text(
        json.dumps(agy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return paths
