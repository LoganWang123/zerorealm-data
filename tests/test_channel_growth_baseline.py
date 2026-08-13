"""Tests for growth channel baseline parsers and aggregation口径."""

from __future__ import annotations

from pathlib import Path

import pytest

from growth.baseline import build_channel_baseline, render_baseline_markdown
from growth.wechat import (
    WechatReportError,
    parse_wechat_tendency_rows,
    parse_wechat_tendency_xls,
)
from growth.zhihu import (
    ZhihuReportError,
    parse_zhihu_daily_csv,
    parse_zhihu_daily_rows,
)

FIXTURES = Path(__file__).parent / "fixtures" / "growth"


def _wechat_rows() -> list[list[object]]:
    return [
        [""] * 16,
        [
            "",
            "数据趋势概况(2026.07.14-2026.08.12)",
            "",
            "",
            "",
            "数据趋势概况(2026.07.14-2026.08.12)",
            "",
            "",
            "",
            "",
            "",
            "数据来源概况(2026.07.14-2026.08.12)",
            "",
            "",
            "",
            "",
        ],
        [
            "",
            "日期",
            "渠道",
            "阅读人数",
            "",
            "日期",
            "分享人数",
            "跳转阅读原文人数",
            "微信收藏人数",
            "发表篇数",
            "",
            "传播渠道",
            "发表日期",
            "内容标题",
            "阅读人数",
            "阅读人数占比",
        ],
        # unique 全部=10; overlapping sources sum to 13
        [
            "",
            "2026-08-01",
            "全部",
            10,
            "",
            "2026-08-01",
            2,
            1,
            0,
            1,
            "",
            "全部",
            "20260801",
            "智能柜周经营复盘表",
            10,
            1.0,
        ],
        [
            "",
            "2026-08-01",
            "搜一搜",
            6,
            "",
            "2026-08-02",
            0,
            0,
            0,
            0,
            "",
            "搜一搜",
            "20260801",
            "智能柜周经营复盘表",
            6,
            0.6,
        ],
        [
            "",
            "2026-08-01",
            "推荐",
            5,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "推荐",
            "20260801",
            "智能柜周经营复盘表",
            5,
            0.5,
        ],
        [
            "",
            "2026-08-01",
            "公众号主页",
            2,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "全部",
            "20260802",
            "零域日报 No.X",
            3,
            0.3,
        ],
        # empty metric cells should become zeros, not crash
        ["", "2026-08-02", "全部", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ]


class TestWechatParser:
    def test_unique_readers_not_sum_of_sources(self):
        summary = parse_wechat_tendency_rows(_wechat_rows())
        assert summary.unique_readers == 10
        assert summary.overlapping_source_readers["搜一搜"] == 6
        assert summary.overlapping_source_readers["推荐"] == 5
        assert summary.overlapping_source_readers["公众号主页"] == 2
        source_sum = sum(summary.overlapping_source_readers.values())
        assert source_sum == 13
        assert source_sum != summary.unique_readers
        assert summary.share_people == 2
        assert summary.original_link_people == 1
        assert summary.favorite_people == 0
        assert summary.published_articles == 1
        assert summary.title_unique_ranking[0].title == "智能柜周经营复盘表"
        assert summary.title_unique_ranking[0].unique_readers == 10

    def test_empty_sheet_rejected(self):
        with pytest.raises(WechatReportError, match="empty"):
            parse_wechat_tendency_rows([])

    def test_bad_headers_rejected(self):
        rows = _wechat_rows()
        rows[2][2] = "来源"
        with pytest.raises(WechatReportError, match="headers"):
            parse_wechat_tendency_rows(rows)

    def test_non_biff_file_rejected(self, tmp_path: Path):
        fake = tmp_path / "not-wechat.xls"
        fake.write_text("日期,阅读\n2026-08-01,1\n", encoding="utf-8")
        with pytest.raises(WechatReportError, match="BIFF"):
            parse_wechat_tendency_xls(fake)

    def test_missing_file_rejected(self, tmp_path: Path):
        with pytest.raises(WechatReportError, match="not found"):
            parse_wechat_tendency_xls(tmp_path / "missing.xls")

    def test_xls_loader_uses_xlrd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        path = tmp_path / "sample.xls"
        path.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 8)

        rows = _wechat_rows()
        col_count = max(len(row) for row in rows)

        class FakeSheet:
            nrows = len(rows)
            ncols = col_count

            def cell_value(self, row_idx: int, col_idx: int):
                row = rows[row_idx]
                return row[col_idx] if col_idx < len(row) else ""

        class FakeBook:
            nsheets = 1

            def sheet_by_index(self, _idx: int):
                return FakeSheet()

        monkeypatch.setattr(
            "growth.wechat.xlrd.open_workbook",
            lambda _path: FakeBook(),
        )
        summary = parse_wechat_tendency_xls(path)
        assert summary.unique_readers == 10


class TestZhihuParser:
    def test_parse_fixture_csv(self):
        summary = parse_zhihu_daily_csv(FIXTURES / "sample_zhihu_daily.csv")
        assert summary.total_reads == 83
        assert summary.total_likes == 2
        assert summary.total_favorites == 1
        assert summary.total_shares == 1
        assert summary.total_comments == 0
        assert summary.nonzero_read_days == 2
        assert summary.peak_date == "2026-08-09"
        assert summary.peak_reads == 53

    def test_empty_metric_cells_become_zero(self):
        summary = parse_zhihu_daily_rows(
            [
                {
                    "日期": "2026-08-03",
                    "阅读": "",
                    "点赞": "",
                    "评论": "",
                    "收藏": "",
                    "分享": "",
                },
                {
                    "日期": "2026-08-04",
                    "阅读": "5",
                    "点赞": "1",
                    "评论": "0",
                    "收藏": "",
                    "分享": "2",
                },
            ]
        )
        assert summary.total_reads == 5
        assert summary.total_likes == 1
        assert summary.total_favorites == 0
        assert summary.total_shares == 2
        assert summary.nonzero_read_days == 1

    def test_empty_file_rejected(self, tmp_path: Path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ZhihuReportError, match="empty"):
            parse_zhihu_daily_csv(path)

    def test_wrong_format_rejected(self, tmp_path: Path):
        path = tmp_path / "bad.csv"
        path.write_text("foo,bar\n1,2\n", encoding="utf-8")
        with pytest.raises(ZhihuReportError):
            parse_zhihu_daily_csv(path)

    def test_biff_binary_rejected(self, tmp_path: Path):
        path = tmp_path / "binary.xls"
        path.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 20)
        with pytest.raises(ZhihuReportError, match="CSV"):
            parse_zhihu_daily_csv(path)


class TestBaselineAssembly:
    def test_build_and_render(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        wechat_path = tmp_path / "wechat.xls"
        wechat_path.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 8)
        zhihu_path = FIXTURES / "sample_zhihu_daily.csv"

        rows = _wechat_rows()
        col_count = max(len(row) for row in rows)

        class FakeSheet:
            nrows = len(rows)
            ncols = col_count

            def cell_value(self, row_idx: int, col_idx: int):
                row = rows[row_idx]
                return row[col_idx] if col_idx < len(row) else ""

        class FakeBook:
            nsheets = 1

            def sheet_by_index(self, _idx: int):
                return FakeSheet()

        monkeypatch.setattr(
            "growth.wechat.xlrd.open_workbook",
            lambda _path: FakeBook(),
        )

        baseline = build_channel_baseline(
            wechat_path=wechat_path,
            zhihu_path=zhihu_path,
            baseline_date="2026-08-12",
            generated_on="2026-08-13",
        )
        assert baseline["privacy"]["raw_reports_copied"] is False
        assert baseline["privacy"]["user_pii_recorded"] is False
        assert baseline["wechat"]["unique_readers_全部"] == 10
        limitations = " ".join(baseline["limitations"])
        assert "因果" in limitations
        assert baseline["experiments_14d"]
        first = baseline["experiments_14d"][0]
        assert any("CTA" in action or "订阅" in action for action in first["actions"])

        markdown = render_baseline_markdown(baseline)
        assert "全部" in markdown
        assert "搜一搜" in markdown
        assert "14 天增长实验" in markdown
        assert "因果" in markdown
