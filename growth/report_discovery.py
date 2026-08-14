"""Discover local WeChat / Zhihu report files without copying them into the repo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from growth.wechat import WechatReportError, parse_wechat_tendency_xls
from growth.zhihu import ZhihuDailySummary, ZhihuReportError, parse_zhihu_daily_csv

ZHIHU_PREFERRED_NAMES = (
    "日报表 (1).xls",
    "日报表（1）.xls",
    "日报表.xls",
)


class ReportDiscoveryError(ValueError):
    """Raised when local channel reports cannot be selected safely."""


@dataclass(frozen=True)
class DiscoveredReport:
    path: Path
    filename: str
    kind: str
    aliases: tuple[str, ...] = ()
    selection_reason: str = ""


def _is_biff_xls(path: Path) -> bool:
    sniff = path.read_bytes()[:8]
    return sniff[:4] == b"\xd0\xcf\x11\xe0"


def discover_wechat_tendency(import_dir: Path | str) -> DiscoveredReport:
    root = Path(import_dir)
    if not root.is_dir():
        raise ReportDiscoveryError(f"import directory not found: {root}")

    candidates = sorted(
        path for path in root.glob("tendency_*.xls") if path.is_file() and _is_biff_xls(path)
    )
    if not candidates:
        raise ReportDiscoveryError(f"no BIFF WeChat tendency_*.xls in {root}")
    chosen = max(candidates, key=lambda path: path.stat().st_mtime)
    aliases = tuple(path.name for path in candidates if path != chosen)
    return DiscoveredReport(
        path=chosen,
        filename=chosen.name,
        kind="wechat_tendency",
        aliases=aliases,
        selection_reason="newest parseable tendency_*.xls (BIFF/OLE)",
    )


def _zhihu_sort_key(path: Path, summary: ZhihuDailySummary) -> tuple:
    preferred_rank = 0
    if path.name in ("日报表 (1).xls", "日报表（1）.xls"):
        preferred_rank = 2
    elif path.name == "日报表.xls":
        preferred_rank = 1
    span = len(summary.daily_rows)
    return (preferred_rank, span, -path.stat().st_mtime)


def discover_zhihu_daily(import_dir: Path | str) -> DiscoveredReport:
    """Prefer the fuller Chrome duplicate `日报表 (1).xls` when equivalent files exist."""
    root = Path(import_dir)
    if not root.is_dir():
        raise ReportDiscoveryError(f"import directory not found: {root}")

    named = [root / name for name in ZHIHU_PREFERRED_NAMES if (root / name).is_file()]
    extras = [
        path
        for path in root.glob("日报表*.xls")
        if path.is_file() and path not in named
    ]
    parsed: list[tuple[Path, ZhihuDailySummary]] = []
    errors: list[str] = []
    for path in named + extras:
        try:
            parsed.append((path, parse_zhihu_daily_csv(path)))
        except ZhihuReportError as exc:
            errors.append(f"{path.name}: {exc}")

    if not parsed:
        detail = "; ".join(errors) if errors else "no 日报表*.xls candidates"
        raise ReportDiscoveryError(f"no parseable Zhihu daily CSV in {root} ({detail})")

    chosen_path, chosen_summary = max(parsed, key=lambda item: _zhihu_sort_key(*item))
    aliases = tuple(path.name for path, _summary in parsed if path != chosen_path)
    reason = (
        "prefer 日报表 (1).xls when present, else longest parseable 日报表*.xls period"
        f" (selected {chosen_path.name}, {len(chosen_summary.daily_rows)} days"
        f" {chosen_summary.period_start}~{chosen_summary.period_end})"
    )
    return DiscoveredReport(
        path=chosen_path,
        filename=chosen_path.name,
        kind="zhihu_daily",
        aliases=aliases,
        selection_reason=reason,
    )


def parse_wechat_or_raise(path: Path | str):
    try:
        return parse_wechat_tendency_xls(path)
    except WechatReportError as exc:
        raise ReportDiscoveryError(str(exc)) from exc
