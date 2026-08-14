"""Tests for freshness-gated local report import and ops retrospective."""

from __future__ import annotations

from pathlib import Path

from growth.freshness import classify_freshness, lag_days
from growth.report_discovery import discover_zhihu_daily
from growth.retrospective import (
    build_ops_retrospective,
    render_ops_retrospective_markdown,
    select_next_work_item,
)
from growth.wechat import WechatTendencySummary
from growth.zhihu import ZhihuDailySummary, ZhihuDailyRow

FIXTURES = Path(__file__).parent / "fixtures" / "growth"
ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "data" / "growth" / "channel-baseline-2026-08-12.json"


def _wechat(*, end: str = "2026-08-12") -> WechatTendencySummary:
    return WechatTendencySummary(
        period_start="2026-07-14",
        period_end=end,
        unique_readers=90,
        overlapping_source_readers={"搜一搜": 47, "推荐": 31},
        share_people=6,
        original_link_people=4,
        favorite_people=0,
        published_articles=12,
    )


def _zhihu(*, end: str = "2026-08-13") -> ZhihuDailySummary:
    return ZhihuDailySummary(
        period_start="2026-07-27",
        period_end=end,
        total_reads=305,
        total_likes=5,
        total_favorites=5,
        total_shares=4,
        total_comments=0,
        nonzero_read_days=11,
        peak_date="2026-08-09",
        peak_reads=53,
        daily_rows=[
            ZhihuDailyRow(end, 0, 0, 0, 0, 0),
        ],
    )


def _baseline() -> dict:
    import json

    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _collection(*, conclusion: str = "success", sources_success: int = 34) -> dict:
    return {
        "run_id": 31817014485,
        "event": "schedule",
        "conclusion": conclusion,
        "html_url": "https://github.com/LoganWang123/zerorealm-data/actions/runs/31817014485",
        "head_sha": "be4739b",
        "collection_date": "2026-08-14",
        "duration_seconds_workflow": 1119,
        "metrics": {
            "sources_total": 51,
            "sources_success": sources_success,
            "sources_failed": 17,
            "items_new": 249,
            "items_total": 1166,
            "items_duplicate": 917,
            "errors": ["36kr_rss: no items returned"],
        },
        "artifact": {"id": 1, "name": "daily-collection-2026-08-14", "size_bytes": 10},
    }


class TestFreshness:
    def test_stale_when_lag_over_one_day(self):
        result = classify_freshness(
            period_end="2026-08-12",
            review_date="2026-08-15",
            experiment_start="2026-08-13",
        )
        assert result["lag_days"] == 3
        assert result["status"] == "stale"
        assert result["covers_experiment_start"] is False
        assert result["can_fill_current_experiment"] is False

    def test_current_when_end_is_yesterday(self):
        result = classify_freshness(
            period_end="2026-08-14",
            review_date="2026-08-15",
            experiment_start="2026-08-13",
        )
        assert lag_days("2026-08-14", "2026-08-15") == 1
        assert result["status"] == "current"
        assert result["covers_experiment_start"] is True
        assert result["can_fill_current_experiment"] is True


class TestZhihuDiscovery:
    def test_prefers_parenthetical_duplicate(self, tmp_path: Path):
        sample = (FIXTURES / "sample_zhihu_daily.csv").read_text(encoding="utf-8")
        (tmp_path / "日报表.xls").write_text(sample, encoding="utf-8")
        fuller = sample + "2026-07-27,1,0,0,0,0,0,0\n"
        (tmp_path / "日报表 (1).xls").write_text(fuller, encoding="utf-8")
        discovered = discover_zhihu_daily(tmp_path)
        assert discovered.filename == "日报表 (1).xls"
        assert "日报表.xls" in discovered.aliases

    def test_accepts_renamed_daily_xls(self, tmp_path: Path):
        sample = (FIXTURES / "sample_zhihu_daily.csv").read_text(encoding="utf-8")
        (tmp_path / "日报表.xls").write_text(sample, encoding="utf-8")
        discovered = discover_zhihu_daily(tmp_path)
        assert discovered.filename == "日报表.xls"


class TestRetrospective:
    def test_stale_reports_do_not_fill_current_experiment(self):
        payload = build_ops_retrospective(
            review_date="2026-08-15",
            baseline=_baseline(),
            wechat=_wechat(),
            zhihu=_zhihu(),
            wechat_filename="tendency_demo.xls",
            zhihu_filename="日报表 (1).xls",
            zhihu_aliases=["日报表.xls"],
            collection=_collection(),
            generated_on="2026-08-15",
        )
        observed = payload["business_channels"]["current_experiment_channel_observed"]
        assert observed["wechat_unique_readers"] is None
        assert payload["business_channels"]["current_experiment_import"]["applied"] is False
        assert payload["fabricated_outcomes"] is False
        assert payload["privacy"]["raw_reports_copied"] is False
        assert payload["next_work_item"]["id"] == "import_fresh_channel_reports_7d"
        assert payload["next_work_item"]["owner_github"] == "LoganWang123"
        assert payload["next_work_item"]["next_review_date"] == "2026-08-22"

        markdown = render_ops_retrospective_markdown(payload)
        assert "技术采集" in markdown
        assert "微信 / 知乎业务指标" in markdown
        assert "虚构成果：**否**" in markdown
        assert "sources_success" in markdown

    def test_failed_collection_selects_repair_item(self):
        item = select_next_work_item(
            review_date="2026-08-15",
            collection_ok=False,
            wechat_freshness={"status": "stale", "covers_experiment_start": False, "period_end": "2026-08-12"},
            experiment_end="2026-08-26",
        )
        assert item["id"] == "repair_daily_collection"

    def test_current_wechat_selects_funnel_item(self):
        item = select_next_work_item(
            review_date="2026-08-15",
            collection_ok=True,
            wechat_freshness={
                "status": "current",
                "covers_experiment_start": True,
                "period_end": "2026-08-14",
            },
            experiment_end="2026-08-26",
        )
        assert item["id"] == "fill_current_funnel_and_evaluate"
