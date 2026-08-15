"""Tests for founder growth ops: scorecard, ledger, combat pack, funnel safety."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from growth.combat_pack import (
    TOOL_PAGE_URL,
    build_combat_pack,
    render_combat_pack_markdown,
)
from growth.ledger import (
    FUNNEL_COUNTER_KEYS,
    FUNNEL_NULLABLE_KEYS,
    FUNNEL_RATE_KEYS,
    FUNNEL_SLOT_KEYS,
    LedgerError,
    compute_funnel_rates,
    default_ledger_template,
    derive_ledger_alerts,
    validate_ledger,
)
from growth.ops import generate_founder_growth_ops, build_weekly_decisions
from growth.outreach import (
    build_outreach_pack,
    empty_target_account_slots,
    render_outreach_markdown,
)
from growth.rates import format_rate, safe_rate
from growth.scorecard import build_founder_scorecard, seed_ledger_from_baseline

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "data" / "growth" / "channel-baseline-2026-08-12.json"


def _mini_baseline() -> dict:
    return {
        "schema_version": 1,
        "baseline_date": "2026-08-12",
        "privacy": {
            "raw_reports_copied": False,
            "user_pii_recorded": False,
            "contents": "aggregates_only",
        },
        "wechat": {
            "period": {"start": "2026-07-14", "end": "2026-08-12"},
            "unique_readers_全部": 90,
            "overlapping_source_readers": {
                "搜一搜": 47,
                "推荐": 31,
                "公众号主页": 19,
            },
            "engagement": {
                "share_people": 6,
                "original_link_people": 4,
                "favorite_people": 0,
                "published_articles": 12,
            },
            "title_unique_ranking": [],
            "notes": [],
        },
        "zhihu": {
            "period": {"start": "2026-07-27", "end": "2026-08-13"},
            "totals": {
                "reads": 305,
                "likes": 5,
                "favorites": 5,
                "shares": 4,
                "comments": 0,
            },
            "nonzero_read_days": 11,
            "peak": {"date": "2026-08-09", "reads": 53},
            "notes": [],
        },
        "experiments_14d": [
            {
                "name": "demo",
                "hypothesis": "h",
                "actions": ["a"],
                "metrics": ["m"],
                "targets": {
                    "content_prep_on_time_rate": "计划内容按期准备率",
                    "keyword_replies": "关键词「复盘表」回复数",
                },
            }
        ],
        "limitations": ["样本很小"],
    }


class TestRates:
    def test_zero_denominator_returns_none(self):
        assert safe_rate(1, 0) is None
        assert safe_rate(0, 0) is None
        assert format_rate(None) == "n/a (zero/missing denominator)"

    def test_missing_denominator_returns_none(self):
        assert safe_rate(1, None) is None
        assert safe_rate(None, None) is None
        assert safe_rate(None, 10) is None

    def test_nonzero_denominator(self):
        assert safe_rate(1, 4) == 0.25
        assert format_rate(0.25, digits=2) == "0.25"


class TestLedgerSchemaAndFunnel:
    def test_template_validates_and_defaults(self):
        ledger = default_ledger_template()
        assert validate_ledger(ledger)["schema_version"] == 1
        assert ledger["privacy"]["raw_reports_copied"] is False
        assert ledger["privacy"]["user_pii_recorded"] is False
        for key in FUNNEL_NULLABLE_KEYS:
            assert ledger["funnel_manual"][key] is None
        for key in FUNNEL_COUNTER_KEYS:
            assert ledger["funnel_manual"][key] == 0
        for key in (
            "wechat_unique_readers",
            "zhihu_reads",
            "wechat_share_people",
        ):
            assert ledger["channel_observed"][key] is None

    def test_exact_event_fields_present(self):
        ledger = default_ledger_template()
        slots = ledger["funnel_manual"]
        for key in (
            "impressions",
            "views",
            "tool_views",
            "keyword_replies",
            "subscribe_click",
            "subscribe_success",
        ):
            assert key in slots
        assert set(FUNNEL_SLOT_KEYS) == set(slots)
        assert "interview_click" not in slots
        assert "interview_completed" not in slots
        assert "public_case_permissions" not in slots

    def test_schema_rejects_pii_flag(self):
        ledger = default_ledger_template()
        ledger["privacy"]["user_pii_recorded"] = True
        with pytest.raises(LedgerError):
            validate_ledger(ledger)

    def test_zero_and_missing_denominator_rates_are_na(self):
        ledger = default_ledger_template()
        funnel = compute_funnel_rates(ledger)
        for key in FUNNEL_RATE_KEYS:
            assert funnel["rates"][key] is None
            assert funnel["rates_display"][key] == "n/a (zero/missing denominator)"
        assert set(funnel["zero_denominator_slots"]) == set(FUNNEL_RATE_KEYS)
        assert "unique_to_tool" not in funnel["rates"]
        assert "tool_to_interview_click" not in funnel["rates"]

    def test_filled_period_rates(self):
        ledger = default_ledger_template()
        ledger["funnel_manual"].update(
            {
                "impressions": 100,
                "views": 40,
                "tool_views": 10,
                "keyword_replies": 5,
                "subscribe_click": 4,
                "subscribe_success": 2,
            }
        )
        funnel = compute_funnel_rates(ledger)
        assert funnel["rates"]["impression_to_view"] == 0.4
        assert funnel["rates"]["view_to_tool"] == 0.25
        assert funnel["rates"]["tool_to_subscribe_click"] == 0.4
        assert funnel["rates"]["subscribe_click_to_success"] == 0.5
        assert funnel["zero_denominator_slots"] == []
        assert funnel["website_event_map"]["tool_views"] == "tool_view"
        assert funnel["counts"]["keyword_replies"] == 5

    def test_anonymous_experiment_targets(self):
        ledger = default_ledger_template()
        targets = ledger["experiment_targets"]
        assert "content_prep_on_time_rate" in targets
        assert "keyword_replies" in targets
        assert "tool_views" in targets
        assert "public_platform_engagement_delta" in targets
        assert "cta_events" not in targets
        blob = json.dumps(targets, ensure_ascii=False)
        assert "访谈" not in blob
        assert "交流线索" not in blob

    def test_overlap_and_attribution_alerts_current_period(self):
        ledger = default_ledger_template()
        ledger["channel_observed"]["wechat_unique_readers"] = 90
        ledger["channel_observed"]["wechat_overlapping_source_readers_sum"] = 103
        ledger["channel_observed"]["zhihu_article_level_attribution_available"] = False
        alerts = derive_ledger_alerts(ledger)
        codes = {item["code"] for item in alerts}
        assert "wechat_source_overlap" in codes
        assert "zhihu_missing_article_attribution" in codes
        overlap = next(item for item in alerts if item["code"] == "wechat_source_overlap")
        assert "禁止相加" in overlap["message"]


class TestScorecard:
    def test_no_cross_period_unique_to_tool_zero(self):
        """Default generate must never produce cross-period unique_to_tool=0."""
        baseline = _mini_baseline()
        seeded = seed_ledger_from_baseline(baseline)
        assert seeded["channel_observed"]["wechat_unique_readers"] is None
        assert seeded["channel_observed"]["zhihu_reads"] is None
        assert seeded["funnel_manual"]["tool_views"] == 0
        funnel = compute_funnel_rates(seeded)
        assert "unique_to_tool" not in funnel["rates"]
        for key, value in funnel["rates"].items():
            assert value is None, f"{key} should be n/a on empty current period"
            assert funnel["rates_display"][key] == "n/a (zero/missing denominator)"

        scorecard = build_founder_scorecard(
            baseline=baseline, generated_on="2026-08-13"
        )
        assert "baseline_snapshot" in scorecard
        assert "current_experiment" in scorecard
        assert scorecard["baseline_snapshot"]["wechat"]["unique_readers_全部"] == 90
        assert (
            scorecard["current_experiment"]["channel_observed"]["wechat_unique_readers"]
            is None
        )
        assert "unique_to_tool" not in scorecard["funnel_rates"]["rates"]
        assert all(
            v is None for v in scorecard["current_experiment"]["funnel_rates"]["rates"].values()
        )

    def test_overlap_not_treated_as_unique(self):
        baseline = _mini_baseline()
        scorecard = build_founder_scorecard(
            baseline=baseline, generated_on="2026-08-13"
        )
        assert scorecard["baseline_snapshot"]["wechat"]["unique_readers_全部"] == 90
        assert (
            scorecard["baseline_snapshot"]["wechat"]["overlapping_source_readers_sum"]
            == 97
        )
        assert (
            scorecard["baseline_snapshot"]["wechat"]["sources_are_unique_people"]
            is False
        )
        assert (
            scorecard["baseline_snapshot"]["zhihu"][
                "article_level_attribution_available"
            ]
            is False
        )
        assert scorecard["target_kind"] == (
            "internal_experiment_goals_not_industry_benchmarks"
        )
        codes = {item["code"] for item in scorecard["alerts"]}
        assert "wechat_source_overlap" in codes
        assert "zhihu_missing_article_attribution" in codes
        # Overlap alert is baseline-scoped; current channel is still null.
        assert any(
            a["code"] == "wechat_source_overlap"
            and a.get("scope") == "baseline_snapshot"
            for a in scorecard["alerts"]
        )
        assert scorecard["privacy"]["raw_reports_copied"] is False
        assert scorecard["privacy"]["user_pii_recorded"] is False

    def test_manual_funnel_slots_present(self):
        scorecard = build_founder_scorecard(
            baseline=_mini_baseline(), generated_on="2026-08-13"
        )
        slots = scorecard["funnel_manual_slots"]
        for key in (
            "impressions",
            "views",
            "tool_views",
            "keyword_replies",
            "subscribe_click",
            "subscribe_success",
        ):
            assert key in slots
        assert "interview_click" not in slots

    def test_seed_ledger_deterministic(self):
        baseline = _mini_baseline()
        a = seed_ledger_from_baseline(baseline)
        b = seed_ledger_from_baseline(baseline)
        assert a == b


class TestCombatPack:
    def test_deterministic_and_budget(self):
        a = build_combat_pack(start_date="2026-08-13")
        b = build_combat_pack(start_date="2026-08-13")
        assert a == b
        assert a["start_date"] == "2026-08-13"
        assert a["end_date"] == "2026-08-26"
        assert a["within_solo_founder_budget"] is True
        hours = a["estimated_hours_per_week"]
        assert 8 <= hours <= 15
        assert all(piece["auto_publish"] is False for piece in a["pieces"])
        themes = {piece["theme"] for piece in a["pieces"]}
        assert "五指标周复盘工具" in themes
        assert "缺货排查" in themes
        assert "运营决策清单" in themes
        assert "self_serve_ops" in a["hour_breakdown"]
        assert "outreach_slots" not in a["hour_breakdown"]
        blob = json.dumps(a, ensure_ascii=False)
        assert "预约运营商访谈" not in blob
        assert "访谈意向" not in blob

    def test_cta_url_and_utm_per_piece(self):
        pack = build_combat_pack(start_date="2026-08-13")
        assert pack["tool_page_url"] == TOOL_PAGE_URL
        for piece in pack["pieces"]:
            assert piece["utm"].startswith(f"utm_source={piece['channel']}")
            assert "utm_campaign=founder14d_20260813" in piece["utm"]
            assert piece["cta_url"] == f"{TOOL_PAGE_URL}?{piece['utm']}"
            assert piece["cta_url"].startswith(TOOL_PAGE_URL)
            assert piece["audience"]
            assert piece["search_intent"]
            assert piece["structure"]
            assert piece["cta"]
            assert "访谈" not in piece["cta"]
            assert "复盘表" in piece["cta"] or "周复盘工具" in piece["cta"]

        # Spot-check known utm_content values.
        by_id = {p["id"]: p for p in pack["pieces"]}
        assert (
            by_id["w1-wechat-five-metrics"]["utm"]
            == "utm_source=wechat&utm_medium=article"
            "&utm_campaign=founder14d_20260813&utm_content=five_metrics_weekly"
        )
        assert by_id["w1-wechat-five-metrics"]["cta_url"].endswith(
            "utm_content=five_metrics_weekly"
        )

    def test_markdown_mentions_no_causal_and_cta_url(self):
        pack = build_combat_pack(start_date="2026-08-13")
        md = render_combat_pack_markdown(pack)
        assert "不从小样本推因果" in md
        assert "不自动发布" in md
        assert TOOL_PAGE_URL in md
        assert "CTA URL（可复制）" in md
        assert "预约运营商访谈" not in md
        for piece in pack["pieces"]:
            assert piece["cta_url"] in md


class TestOutreach:
    def test_empty_slots_no_fabricated_names(self):
        slots = empty_target_account_slots(week_label="2026-W33", count=4)
        assert len(slots) == 4
        assert all(slot.get("surface", "") == "" for slot in slots)
        assert all(slot["status"] == "empty" for slot in slots)
        assert all("访谈" not in slot["ask"] for slot in slots)

    def test_slots_bounds(self):
        with pytest.raises(ValueError):
            empty_target_account_slots(week_label="x", count=2)
        pack = build_outreach_pack(slots_per_week=3)
        assert len(pack["weekly_target_slots"]["2026-W33"]) == 3
        assert "professional_boundaries" in pack
        assert "interview_template" not in pack
        md = render_outreach_markdown(pack)
        assert "职业边界" in md
        assert "复盘表" in md
        assert "预约运营商访谈" not in md


class TestOpsBundle:
    def test_generate_bundle_deterministic_no_cross_period_zero(self):
        baseline = _mini_baseline()
        a = generate_founder_growth_ops(
            baseline=baseline,
            start_date="2026-08-13",
            generated_on="2026-08-13",
        )
        b = generate_founder_growth_ops(
            baseline=baseline,
            start_date="2026-08-13",
            generated_on="2026-08-13",
        )
        assert a["scorecard"] == b["scorecard"]
        assert a["combat_pack"] == b["combat_pack"]
        assert "unique_to_tool" not in a["funnel"]["rates"]
        assert all(v is None for v in a["funnel"]["rates"].values())
        assert a["ledger"]["channel_observed"]["wechat_unique_readers"] is None
        decisions = a["weekly_decisions"]["decisions"]
        ids = {item["id"] for item in decisions}
        assert "use_unique_readers_only" in ids
        assert "no_auto_publish" in ids
        assert "use_piece_cta_url" in ids
        assert "self_serve_funnel_only" in ids
        assert "outreach_empty_slots" not in ids
        decision_blob = json.dumps(decisions, ensure_ascii=False)
        assert "预约运营商访谈" not in decision_blob

    def test_real_baseline_file_if_present(self):
        if not BASELINE_PATH.is_file():
            pytest.skip("baseline artifact not present")
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        bundle = generate_founder_growth_ops(
            baseline=baseline,
            start_date="2026-08-13",
            generated_on="2026-08-13",
        )
        assert bundle["privacy"]["raw_reports_copied"] is False
        assert (
            bundle["scorecard"]["baseline_snapshot"]["wechat"][
                "sources_are_unique_people"
            ]
            is False
        )
        assert (
            bundle["scorecard"]["current_experiment"]["channel_observed"][
                "wechat_unique_readers"
            ]
            is None
        )
        codes = {item["code"] for item in bundle["scorecard"]["alerts"]}
        assert "zhihu_missing_article_attribution" in codes
        assert "wechat_source_overlap" in codes
        # Must not invent unique_to_tool=0 from baseline unique=90 + tool=0.
        assert "unique_to_tool" not in bundle["funnel"]["rates"]
        assert all(
            display.startswith("n/a")
            for display in bundle["funnel"]["rates_display"].values()
        )
        assert "interview_click" not in bundle["ledger"]["funnel_manual"]
        targets = bundle["ledger"]["experiment_targets"]
        assert "keyword_replies" in targets
        assert "cta_events" not in targets

    def test_weekly_decisions_include_funnel_display(self):
        baseline = _mini_baseline()
        bundle = generate_founder_growth_ops(
            baseline=baseline, generated_on="2026-08-13"
        )
        decisions = build_weekly_decisions(
            scorecard=bundle["scorecard"],
            combat_pack=bundle["combat_pack"],
            funnel=bundle["funnel"],
        )
        assert "n/a (zero/missing denominator)" in decisions["funnel_rates_display"].values()
