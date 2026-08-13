"""Parse Zhihu creator daily CSV exports (often misnamed .xls)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = ("日期", "阅读", "点赞", "评论", "收藏", "分享")


class ZhihuReportError(ValueError):
    """Raised when a Zhihu daily CSV cannot be parsed."""


@dataclass(frozen=True)
class ZhihuDailyRow:
    date: str
    reads: int
    likes: int
    comments: int
    favorites: int
    shares: int


@dataclass
class ZhihuDailySummary:
    period_start: str
    period_end: str
    total_reads: int
    total_likes: int
    total_favorites: int
    total_shares: int
    total_comments: int
    nonzero_read_days: int
    peak_date: str | None
    peak_reads: int
    daily_rows: list[ZhihuDailyRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": {"start": self.period_start, "end": self.period_end},
            "totals": {
                "reads": self.total_reads,
                "likes": self.total_likes,
                "favorites": self.total_favorites,
                "shares": self.total_shares,
                "comments": self.total_comments,
            },
            "nonzero_read_days": self.nonzero_read_days,
            "peak": {
                "date": self.peak_date,
                "reads": self.peak_reads,
            },
            "notes": list(self.notes),
        }


def _as_int(value: Any, *, field_name: str) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise ZhihuReportError(f"non-numeric {field_name}: {value!r}") from exc


def parse_zhihu_daily_rows(rows: list[dict[str, str]]) -> ZhihuDailySummary:
    if not rows:
        raise ZhihuReportError("zhihu daily csv has no data rows")

    missing = [name for name in REQUIRED_COLUMNS if name not in rows[0]]
    if missing:
        raise ZhihuReportError(f"zhihu csv missing columns: {missing}")

    parsed: list[ZhihuDailyRow] = []
    for raw in rows:
        date = (raw.get("日期") or "").strip()
        if not date:
            # Skip blank trailing lines; keep empty metric cells as zeros.
            if not any((raw.get(col) or "").strip() for col in REQUIRED_COLUMNS[1:]):
                continue
            raise ZhihuReportError("zhihu row missing date")
        parsed.append(
            ZhihuDailyRow(
                date=date,
                reads=_as_int(raw.get("阅读"), field_name="阅读"),
                likes=_as_int(raw.get("点赞"), field_name="点赞"),
                comments=_as_int(raw.get("评论"), field_name="评论"),
                favorites=_as_int(raw.get("收藏"), field_name="收藏"),
                shares=_as_int(raw.get("分享"), field_name="分享"),
            )
        )

    if not parsed:
        raise ZhihuReportError("zhihu daily csv has no usable rows")

    ordered = sorted(parsed, key=lambda item: item.date)
    nonzero = [item for item in ordered if item.reads > 0]
    peak = max(ordered, key=lambda item: (item.reads, item.date))

    notes = [
        "知乎日报表仅为账号级日汇总，缺少文章级归因，不能推断单篇内容因果效果。",
        "输出仅保留聚合指标与峰值日，不写入原始账号明细以外的用户个人信息。",
    ]

    return ZhihuDailySummary(
        period_start=ordered[0].date,
        period_end=ordered[-1].date,
        total_reads=sum(item.reads for item in ordered),
        total_likes=sum(item.likes for item in ordered),
        total_favorites=sum(item.favorites for item in ordered),
        total_shares=sum(item.shares for item in ordered),
        total_comments=sum(item.comments for item in ordered),
        nonzero_read_days=len(nonzero),
        peak_date=peak.date if peak.reads > 0 else None,
        peak_reads=peak.reads,
        daily_rows=ordered,
        notes=notes,
    )


def parse_zhihu_daily_csv(path: Path | str) -> ZhihuDailySummary:
    """Load a Zhihu daily CSV (UTF-8 / UTF-8-SIG), even if the suffix is .xls."""
    report_path = Path(path)
    if not report_path.is_file():
        raise ZhihuReportError(f"zhihu report not found: {report_path}")

    raw = report_path.read_bytes()
    if not raw.strip():
        raise ZhihuReportError("zhihu report is empty")

    # Reject OLE/BIFF binaries; this path expects CSV text.
    if raw[:4] == b"\xd0\xcf\x11\xe0":
        raise ZhihuReportError("zhihu parser expects CSV text, got BIFF/OLE .xls")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ZhihuReportError("zhihu report is not UTF-8 text") from exc

    sample = text.lstrip("\ufeff")[:200]
    if "日期" not in sample or "," not in sample:
        raise ZhihuReportError("zhihu report does not look like a daily CSV")

    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise ZhihuReportError("zhihu csv missing header")

    rows = [dict(row) for row in reader]
    return parse_zhihu_daily_rows(rows)
