"""Parse WeChat Official Account tendency BIFF .xls exports (xlrd)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import xlrd

UNIQUE_CHANNEL = "全部"
SOURCE_CHANNELS_ORDER = (
    "搜一搜",
    "推荐",
    "公众号主页",
    "聊天会话",
    "公众号消息",
    "朋友圈",
    "其他",
)


class WechatReportError(ValueError):
    """Raised when a WeChat tendency workbook cannot be parsed."""


@dataclass(frozen=True)
class WechatTitleReads:
    title: str
    publish_date: str
    unique_readers: int


@dataclass
class WechatTendencySummary:
    period_start: str
    period_end: str
    unique_readers: int
    overlapping_source_readers: dict[str, int] = field(default_factory=dict)
    share_people: int = 0
    original_link_people: int = 0
    favorite_people: int = 0
    published_articles: int = 0
    title_unique_ranking: list[WechatTitleReads] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": {"start": self.period_start, "end": self.period_end},
            "unique_readers_全部": self.unique_readers,
            "overlapping_source_readers": dict(self.overlapping_source_readers),
            "engagement": {
                "share_people": self.share_people,
                "original_link_people": self.original_link_people,
                "favorite_people": self.favorite_people,
                "published_articles": self.published_articles,
            },
            "title_unique_ranking": [
                {
                    "title": item.title,
                    "publish_date": item.publish_date,
                    "unique_readers": item.unique_readers,
                }
                for item in self.title_unique_ranking
            ],
            "notes": list(self.notes),
        }


def _as_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        raise WechatReportError(f"unexpected boolean metric: {value!r}")
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise WechatReportError(f"non-numeric metric: {value!r}") from exc


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_period(label: str) -> tuple[str, str]:
    # e.g. 数据趋势概况(2026.07.14-2026.08.12)
    if "(" not in label or ")" not in label:
        raise WechatReportError(f"missing period label: {label!r}")
    inner = label[label.find("(") + 1 : label.rfind(")")]
    if "-" not in inner:
        raise WechatReportError(f"invalid period label: {label!r}")
    start_raw, end_raw = inner.split("-", 1)
    start = start_raw.strip().replace(".", "-")
    end = end_raw.strip().replace(".", "-")
    if len(start) != 10 or len(end) != 10:
        raise WechatReportError(f"invalid period dates: {label!r}")
    return start, end


def _normalize_publish_date(value: Any) -> str:
    text = _as_text(value)
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def parse_wechat_tendency_rows(rows: list[list[Any]]) -> WechatTendencySummary:
    """Aggregate a WeChat tendency sheet represented as row matrices."""
    if not rows or len(rows) < 3:
        raise WechatReportError("wechat tendency sheet is empty or incomplete")

    period_label = _as_text(rows[1][1] if len(rows[1]) > 1 else "")
    if not period_label:
        raise WechatReportError("wechat tendency period header missing")
    period_start, period_end = _parse_period(period_label)

    header = rows[2] if len(rows) > 2 else []
    expected = ("日期", "渠道", "阅读人数")
    got = tuple(_as_text(header[i]) if len(header) > i else "" for i in (1, 2, 3))
    if got != expected:
        raise WechatReportError(f"unexpected left headers: {got!r}")

    channel_totals: dict[str, int] = defaultdict(int)
    share_people = 0
    original_link_people = 0
    favorite_people = 0
    published_articles = 0
    title_unique: dict[str, WechatTitleReads] = {}

    for row in rows[3:]:
        if len(row) <= 3:
            continue

        left_date = _as_text(row[1])
        left_channel = _as_text(row[2])
        if left_date and left_channel:
            channel_totals[left_channel] += _as_int(row[3])

        if len(row) > 9 and _as_text(row[5]):
            share_people += _as_int(row[6])
            original_link_people += _as_int(row[7])
            favorite_people += _as_int(row[8])
            published_articles += _as_int(row[9])

        if len(row) > 14:
            source = _as_text(row[11])
            title = _as_text(row[13])
            if source == UNIQUE_CHANNEL and title:
                title_unique[title] = WechatTitleReads(
                    title=title,
                    publish_date=_normalize_publish_date(row[12]),
                    unique_readers=_as_int(row[14]),
                )

    if UNIQUE_CHANNEL not in channel_totals:
        raise WechatReportError("missing 全部 channel rows for unique readers")

    unique_readers = channel_totals[UNIQUE_CHANNEL]
    overlapping = {
        name: channel_totals.get(name, 0)
        for name in SOURCE_CHANNELS_ORDER
        if name in channel_totals
    }
    source_sum = sum(overlapping.values())

    ranking = sorted(
        title_unique.values(),
        key=lambda item: (-item.unique_readers, item.publish_date, item.title),
    )
    ranking_sum = sum(item.unique_readers for item in ranking)
    if ranking and ranking_sum != unique_readers:
        # Keep going; surface inconsistency as a note for operators.
        pass

    notes = [
        "微信“全部”阅读人数是去重后的唯一阅读者口径，不可用来源渠道阅读人数相加替代。",
        f"本样本来源渠道阅读人数合计为 {source_sum}，高于“全部”{unique_readers}，"
        "说明来源归因可重叠。",
        "输出仅为聚合指标与标题级排名，不含原始明细行或用户个人信息。",
    ]

    return WechatTendencySummary(
        period_start=period_start,
        period_end=period_end,
        unique_readers=unique_readers,
        overlapping_source_readers=overlapping,
        share_people=share_people,
        original_link_people=original_link_people,
        favorite_people=favorite_people,
        published_articles=published_articles,
        title_unique_ranking=ranking,
        notes=notes,
    )


def parse_wechat_tendency_xls(path: Path | str) -> WechatTendencySummary:
    """Load a WeChat BIFF .xls tendency export and return aggregate metrics."""
    report_path = Path(path)
    if not report_path.is_file():
        raise WechatReportError(f"wechat report not found: {report_path}")

    sniff = report_path.read_bytes()[:8]
    # BIFF/OLE Compound Document magic
    if sniff[:4] != b"\xd0\xcf\x11\xe0":
        raise WechatReportError(
            "wechat report is not a BIFF/OLE .xls workbook "
            f"(got magic={sniff!r})"
        )

    try:
        book = xlrd.open_workbook(str(report_path))
    except xlrd.XLRDError as exc:
        raise WechatReportError(f"failed to open wechat xls: {exc}") from exc

    if book.nsheets < 1:
        raise WechatReportError("wechat workbook has no sheets")

    sheet = book.sheet_by_index(0)
    if sheet.nrows == 0:
        raise WechatReportError("wechat sheet is empty")

    rows = [
        [sheet.cell_value(row_idx, col_idx) for col_idx in range(sheet.ncols)]
        for row_idx in range(sheet.nrows)
    ]
    return parse_wechat_tendency_rows(rows)
