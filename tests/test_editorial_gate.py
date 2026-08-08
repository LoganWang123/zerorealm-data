"""Tests for the Production Editorial Hard Gate (publishing/editorial_gate.py).

Covers the heuristic scanners directly plus the pipeline wiring
(EditorialGateStep) that refuses to proceed toward render/publish when the
hard gate fails, per docs/reports/production-editorial-audit-2026-08-08.md.
"""

from __future__ import annotations

import logging
from datetime import date

from publishing.article import Article, ArticleMeta
from publishing.config import PublishConfig
from publishing.editorial_gate import (
    EditorialGateErrorCode as Code,
    is_bypass_allowed,
    run_daily_editorial_gate,
)
from publishing.manifest_repository import ManifestRepository
from publishing.models import RenderContext
from publishing.pipeline import PipelineContext, PipelineState, StepStatus
from publishing.steps import EditorialGateStep


# ---------------------------------------------------------------------------
# Fixtures — representative Daily payloads
# ---------------------------------------------------------------------------


def _single_signal_daily_with_sources() -> dict:
    """Beijing 2026-08-01 style: one core signal, disclosed source, no predictions."""
    return {
        "title": "北京快递、外卖电动车专用号牌新规施行：相关智能柜补货需核查运力合规与时效",
        "date": "2026-08-01",
        "issue": 10,
        "signal": "北京市快递、外卖行业非机动车管理办法于 8 月 1 日施行。",
        "sections": [
            {
                "level": "core",
                "title": "北京快递、外卖行业电动自行车实行专用号牌管理",
                "excerpt": "北京市商务局等四部门发布的办法自 2026 年 8 月 1 日起施行。",
                "spread_line": "对使用电动自行车补货或接入即时配送的业务，应先核验车辆和运力。",
                "insight": "影响集中在两类场景：自行以电动自行车补货，或依赖即时配送运力补货。",
                "verdict": "核对北京区域相关线路、车辆号牌状态与近 3 个高峰时段到柜及时率。",
                "source_url": "https://sw.beijing.gov.cn/zwxx/2024zcwj/202607/t20260728_4793311.html",
                "source_name": "北京市商务局等四部门",
            }
        ],
        "decision": {
            "operators": {
                "evidence": "北京市快递、外卖行业非机动车管理办法自 2026 年 8 月 1 日施行。",
                "metric": "北京相关线路高峰时段到柜及时率，以及车辆专用号牌登记完成率。",
                "action": "筛选使用电动自行车或即时配送补货的北京线路，核对车辆号牌与合规状态。",
                "sample": "北京区域相关补货线路，连续 3 个高峰时段。",
                "kpi": "当日完成相关线路台账核查并形成异常清单。",
                "stop_condition": "不存在相关运力依赖，或核查后车辆合规且时效未下降时，不扩大整改范围。",
            }
        },
        "tomorrow": ["合作即时配送服务商是否已完成专用号牌与档案管理核验。"],
    }


def _dongpeng_style_channel_inference_daily() -> dict:
    """Single-company earnings stretched into a channel/终端动销 claim, no hedge."""
    return {
        "title": "某饮料公司上半年营收增长18%，渠道动销全面走强",
        "date": "2026-07-30",
        "sections": [
            {
                "level": "core",
                "title": "某饮料公司上半年营收增长18%",
                "excerpt": "某饮料公司披露半年报：营业收入同比增长 18.0%，渠道动销全面走强。",
                "insight": "全国终端动销加速，运营商可放心跟进新品铺货。",
                "verdict": "建议全面扩大该品类 SKU 铺货。",
                "source_url": "https://example.com/half-year-report",
                "source_name": "示例财经",
            }
        ],
    }


def _claim_evidence_contradiction_daily() -> dict:
    """Body asserts channel strength as fact while tomorrow admits data is undisclosed."""
    return {
        "title": "渠道动销加速，运营商应加快铺货节奏",
        "date": "2026-07-30",
        "sections": [
            {
                "level": "core",
                "title": "渠道动销加速的信号已经出现",
                "excerpt": "多方信息显示渠道动销加速，终端旺销趋势明确。",
                "insight": "渠道动销加速已是既成事实，运营商应立即跟进。",
                "verdict": "本周内完成新品铺货计划。",
                "source_url": "https://example.com/news",
                "source_name": "示例媒体",
            }
        ],
        "tomorrow": ["该品牌具体渠道销售数据尚未披露，需持续关注。"],
    }


def _unlabeled_threshold_daily() -> dict:
    """Numeric experiment threshold presented as a fixed universal rule."""
    return {
        "title": "补货规则调整可降低库存",
        "date": "2026-07-30",
        "sections": [
            {
                "level": "core",
                "title": "补货规则调整可降低库存",
                "excerpt": "内部测试显示调整补货规则可以改善库存周转。",
                "insight": "选 10 台柜观察 7 天。",
                "verdict": "只要单品毛利低于30%，就应立即下架，全体运营商应统一执行。",
                "source_url": "https://example.com/test",
                "source_name": "示例来源",
            }
        ],
    }


def _multi_signal_with_predictions_daily() -> dict:
    """Two core signals + a pseudo-precise, unsourced prediction."""
    return {
        "title": "两条核心信号同时出现",
        "date": "2026-07-28",
        "sections": [
            {
                "level": "core",
                "title": "信号一：新华书店入驻闪购",
                "excerpt": "全国约12000家新华书店已入驻美团闪购。",
                "prediction": {
                    "content": "京东跟进图书小时达",
                    "confidence_pct": 70,
                },
                "source_url": "https://example.com/a",
                "source_name": "示例来源A",
            },
            {
                "level": "core",
                "title": "信号二：Gap重启香水系列",
                "excerpt": "Gap宣布重启经典香水系列。",
                "source_url": "https://example.com/b",
                "source_name": "示例来源B",
            },
        ],
    }


def _manual_reviewed_multi_signal_daily() -> dict:
    """manual_reviewed=True but no editorial_exception; still has a hard failure."""
    data = _multi_signal_with_predictions_daily()
    data["manual_reviewed"] = True
    data["gate_status"] = "passed"  # legacy/human label; must NOT bypass the hard gate
    return data


# ---------------------------------------------------------------------------
# Scanner-level tests
# ---------------------------------------------------------------------------


def test_dongpeng_style_channel_inference_fails():
    result = run_daily_editorial_gate(_dongpeng_style_channel_inference_daily())

    assert result.status == "failed"
    assert Code.UNSUPPORTED_CHANNEL_INFERENCE in result.error_codes


def test_claim_evidence_contradiction_fails():
    result = run_daily_editorial_gate(_claim_evidence_contradiction_daily())

    assert result.status == "failed"
    assert Code.CLAIM_EVIDENCE_CONTRADICTION in result.error_codes


def test_unlabeled_threshold_fails():
    result = run_daily_editorial_gate(_unlabeled_threshold_daily())

    assert result.status == "failed"
    assert Code.UNSUPPORTED_THRESHOLD in result.error_codes


def test_single_signal_daily_with_sources_passes():
    result = run_daily_editorial_gate(_single_signal_daily_with_sources())

    assert result.status == "passed"
    assert result.errors == []


def test_observational_lookback_in_sample_does_not_fail():
    """Decision sample lookbacks like '近 7 天报表' are not unlabeled experiment scales."""
    data = _single_signal_daily_with_sources()
    data["decision"]["operators"]["sample"] = (
        "选取主营智能柜点位对应的运营看板与近 7 天过程指标报表。"
    )
    result = run_daily_editorial_gate(data)
    assert result.status == "passed"
    assert Code.UNLABELED_EXPERIMENT_PARAMETER not in result.error_codes


def test_suggested_experiment_label_passes_count_params():
    """'建议试验起点' (website PASS_WITH_EDIT wording) must satisfy LABEL_MARKERS."""
    data = {
        "title": "一项覆盖59,000+台机器的实验提示：人工改补货单要设上限",
        "date": "2026-07-29",
        "sections": [
            {
                "level": "core",
                "title": "有限下调更稳",
                "excerpt": "研究团队在一家中国智能售货运营商开展46天随机实验。",
                "insight": (
                    "这项研究覆盖553名一线补货员、59,000多台机器。"
                    "选20台同类型柜，观察7天（建议试验起点，非行业标准）。"
                ),
                "verdict": "先限制每台柜最多下调2个SKU，用7天对照数据判断。",
                "source_url": "https://arxiv.org/abs/2607.00420",
                "source_name": "arXiv",
            }
        ],
        "decision": {
            "operators": {
                "evidence": "随机实验中有限下调使库存下降且未伤销售。",
                "metric": "缺货率、剩余库存金额",
                "action": "测试组每台柜每次最多向下调整2个SKU（建议试验起点，非行业标准）。",
                "sample": "20台同类型柜观察7天（建议试验起点，非行业标准）。",
                "kpi": "测试组库存下降且缺货率不升。",
                "stop_condition": "缺货率上升时立即恢复原规则。",
            }
        },
    }
    result = run_daily_editorial_gate(data)
    assert result.status == "passed"
    assert Code.UNLABELED_EXPERIMENT_PARAMETER not in result.error_codes
    # Mixed paper N vs sample N may warn, but must not hard-fail.
    assert Code.RESEARCH_COUNT_INCONSISTENT not in result.error_codes


def test_multi_signal_with_predictions_fails():
    result = run_daily_editorial_gate(_multi_signal_with_predictions_daily())

    assert result.status == "failed"
    assert Code.MULTI_SIGNAL_DAILY in result.error_codes
    assert Code.UNSOURCED_PREDICTION in result.error_codes or Code.PSEUDO_PRECISION in result.error_codes


def test_manual_reviewed_alone_does_not_bypass_hard_failure():
    data = _manual_reviewed_multi_signal_daily()
    result = run_daily_editorial_gate(data)

    assert result.status == "failed"
    assert Code.MULTI_SIGNAL_DAILY in result.error_codes
    # manual_reviewed / gate_status flags alone must not waive a hard failure.
    assert is_bypass_allowed(data, result) is False


def test_editorial_exception_bypasses_bypassable_error():
    data = _multi_signal_with_predictions_daily()
    data["editorial_exception"] = {
        "reason": "Known one-off double-signal for a breaking event, approved by editor-in-chief.",
        "approved_at": "2026-07-28T09:00:00+08:00",
    }
    result = run_daily_editorial_gate(data)

    assert result.status == "failed"
    assert is_bypass_allowed(data, result) is True


def test_editorial_exception_cannot_bypass_non_bypassable_error():
    data = _dongpeng_style_channel_inference_daily()
    # Drop the source_url to also trigger the non-bypassable SOURCE_LINEAGE_INCOMPLETE.
    data["sections"][0]["source_url"] = ""
    data["editorial_exception"] = {
        "reason": "Editor approved despite missing source.",
        "approved_at": "2026-07-30T09:00:00+08:00",
    }
    result = run_daily_editorial_gate(data)

    assert Code.SOURCE_LINEAGE_INCOMPLETE in result.error_codes
    assert is_bypass_allowed(data, result) is False


def test_future_publication_fails():
    data = _single_signal_daily_with_sources()
    data["date"] = "2099-01-01"
    result = run_daily_editorial_gate(data, now=date(2026, 8, 8))

    assert result.status == "failed"
    assert Code.FUTURE_PUBLICATION in result.error_codes


def test_source_lineage_incomplete_for_core_item_without_source_url():
    data = _single_signal_daily_with_sources()
    data["sections"][0]["source_url"] = ""
    result = run_daily_editorial_gate(data)

    assert result.status == "failed"
    assert Code.SOURCE_LINEAGE_INCOMPLETE in result.error_codes


def test_overgeneralized_headline_flagged():
    data = _single_signal_daily_with_sources()
    data["title"] = "59,000台柜实验证明：人工改补货单要设上限"
    result = run_daily_editorial_gate(data)

    assert result.status == "failed"
    assert Code.OVERGENERALIZED_HEADLINE in result.error_codes


# ---------------------------------------------------------------------------
# Pipeline wiring — EditorialGateStep blocks BEFORE render/publish
# ---------------------------------------------------------------------------


def _pipeline_context(article: Article, tmp_path) -> PipelineContext:
    manifest = ManifestRepository(tmp_path / "manifest.json")
    return PipelineContext(
        article=article,
        target=None,  # not reached: gate step short-circuits before Render/Publish
        render_context=RenderContext(config=PublishConfig(), asset_manager=None),
        mode="draft",
        trace_id="test-trace",
        config=PublishConfig(),
        manifest=manifest,
        logger=logging.getLogger("test.editorial_gate"),
    )


def _daily_article(raw: dict) -> Article:
    return Article(
        metadata=ArticleMeta(uuid="u1", slug="daily-x", source="daily", issue=1),
        title=str(raw.get("title", "")),
        date=str(raw.get("date", "")),
        raw=raw,
    )


def test_editorial_gate_step_blocks_multi_signal_daily(tmp_path):
    article = _daily_article(_multi_signal_with_predictions_daily())
    ctx = _pipeline_context(article, tmp_path)

    result = EditorialGateStep().execute(ctx)

    assert result.status == StepStatus.FAILED
    assert "MULTI_SIGNAL_DAILY" in result.message
    gate_result = ctx.get(PipelineState.EDITORIAL_GATE_RESULT)
    assert gate_result.status == "failed"


def test_editorial_gate_step_manual_reviewed_still_fails_publish(tmp_path):
    """Manual review flags alone must NOT bypass a hard gate failure."""
    article = _daily_article(_manual_reviewed_multi_signal_daily())
    ctx = _pipeline_context(article, tmp_path)

    result = EditorialGateStep().execute(ctx)

    assert result.status == StepStatus.FAILED


def test_editorial_gate_step_passes_single_signal_daily(tmp_path):
    article = _daily_article(_single_signal_daily_with_sources())
    ctx = _pipeline_context(article, tmp_path)

    result = EditorialGateStep().execute(ctx)

    assert result.status == StepStatus.SUCCESS


def test_editorial_gate_step_skips_non_daily_source(tmp_path):
    article = Article(
        metadata=ArticleMeta(uuid="u1", slug="deep-insight-x", source="deep_insight", issue=1),
        title="research",
        date="2026-07-30",
        raw={"sections": [{"level": "core"}, {"level": "core"}]},  # would fail if checked
    )
    ctx = _pipeline_context(article, tmp_path)

    result = EditorialGateStep().execute(ctx)

    assert result.status == StepStatus.SUCCESS
    assert "skipped" in result.message.lower()


def test_editorial_gate_step_skips_article_without_raw_frontmatter(tmp_path):
    """Programmatically-built Article (no ArticleParser.parse) is left untouched."""
    article = Article(
        metadata=ArticleMeta(uuid="u1", slug="daily-x", source="daily", issue=1),
        title="t",
        date="2026-07-30",
    )
    ctx = _pipeline_context(article, tmp_path)

    result = EditorialGateStep().execute(ctx)

    assert result.status == StepStatus.SUCCESS


def test_editorial_gate_step_bypasses_with_valid_editorial_exception(tmp_path):
    raw = _multi_signal_with_predictions_daily()
    raw["editorial_exception"] = {
        "reason": "Approved one-off exception for a breaking dual-signal event.",
        "approved_at": "2026-07-28T09:00:00+08:00",
    }
    article = _daily_article(raw)
    ctx = _pipeline_context(article, tmp_path)

    result = EditorialGateStep().execute(ctx)

    assert result.status == StepStatus.SUCCESS
    assert "bypassed" in result.message.lower()
