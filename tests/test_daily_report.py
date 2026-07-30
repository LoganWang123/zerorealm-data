"""Tests for generators/daily_report.py — E2E with mock LLM."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest
import yaml

from generators.daily_report import (
    _compose_system_prompt,
    _load_output_template,
    DuplicateDailyReportError,
    GeneratedReportQualityError,
    find_duplicate_headline,
    load_daily_items,
    format_materials,
    next_issue_number,
    published_source_urls,
    parse_llm_response,
    generate_mdx,
    generate_daily_report,
    validate_generated_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_LLM_RESPONSE = """```yaml
summary:
  - "友宝完成C轮融资"
  - "智能柜市场突破百亿"
  - "九部门发布零售创新意见"
sections:
  - type: "industry"
    items:
      - title: "智能柜市场突破百亿"
        excerpt: "智能柜市场在2026年迎来爆发期。市场规模预计突破百亿元。"
        source_url: "https://example.com/1"
        source_name: "联商网"
  - type: "enterprise"
    items:
      - title: "友宝完成C轮融资"
        excerpt: "友宝在线宣布完成C轮融资。估值超50亿元。"
        source_url: "https://example.com/2"
        source_name: "36氪"
  - type: "ai_frontier"
    items:
      - title: "商汤发布视觉芯片"
        excerpt: "商汤科技发布新一代视觉识别芯片。面向零售场景。"
        source_url: "https://example.com/3"
        source_name: "商汤科技"
```"""


@pytest.fixture
def data_dir(tmp_path):
    """Create a mock data directory with raw JSON items."""
    date_path = tmp_path / "raw" / "2026" / "07" / "26"
    date_path.mkdir(parents=True)

    items = [
        {
            "id": "item1",
            "source": "36kr_rss",
            "source_type": "rss",
            "language": "zh-CN",
            "title": "友宝完成C轮融资，估值超50亿元",
            "url": "https://36kr.com/p/1",
            "published_at": "2026-07-26T08:00:00+08:00",
            "crawled_at": "2026-07-26T09:00:00+08:00",
            "run_id": "test",
            "crawl_status": "success",
            "http_status": 200,
            "content_html": "",
            "content_text": "友宝在线宣布完成C轮融资。",
            "summary": "友宝完成融资。",
            "author": "",
            "tags": [],
            "metadata": {"category": "news", "score": 80, "boost_score": 15, "boost_level": "star", "boost_matched": ["core:无人零售"]},
        },
        {
            "id": "item2",
            "source": "linkshop_web",
            "source_type": "web",
            "language": "zh-CN",
            "title": "智能柜行业迎来爆发期",
            "url": "https://linkshop.com/1",
            "published_at": "2026-07-26T07:00:00+08:00",
            "crawled_at": "2026-07-26T09:00:00+08:00",
            "run_id": "test",
            "crawl_status": "success",
            "http_status": 200,
            "content_html": "",
            "content_text": "智能柜市场快速增长。",
            "summary": "智能柜市场爆发。",
            "author": "",
            "tags": [],
            "metadata": {"category": "news", "score": 80, "boost_score": 10, "boost_level": "star", "boost_matched": ["core:智能柜"]},
        },
    ]

    for item in items:
        path = date_path / f"{item['source']}_{item['id']}.json"
        path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

    return str(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadDailyItems:
    def test_loads_items(self, data_dir):
        items = load_daily_items(data_dir, "2026/07/26")
        assert len(items) == 2

    def test_empty_date(self, data_dir):
        items = load_daily_items(data_dir, "2020/01/01")
        assert items == []


class TestParseLlmResponse:
    def test_parses_yaml_block(self):
        parsed = parse_llm_response(MOCK_LLM_RESPONSE)
        assert "summary" in parsed
        assert "sections" in parsed
        assert len(parsed["summary"]) == 3
        assert len(parsed["sections"]) == 3

    def test_section_types(self):
        parsed = parse_llm_response(MOCK_LLM_RESPONSE)
        types = [s["type"] for s in parsed["sections"]]
        assert "industry" in types
        assert "enterprise" in types


class TestGenerateMdx:
    def test_produces_frontmatter(self):
        parsed = parse_llm_response(MOCK_LLM_RESPONSE)
        mdx = generate_mdx(parsed, issue=1, date="2026-07-26")
        assert mdx.startswith("---\n")
        assert "零域日报 No.1" in mdx
        assert "2026-07-26" in mdx


class TestGenerateDailyReport:
    def test_e2e_with_mock_llm(self, data_dir, tmp_path):
        """Full E2E: load items → format → mock LLM → parse → MDX."""
        output_dir = str(tmp_path / "output")

        with patch("generators.daily_report.call_llm", return_value=MOCK_LLM_RESPONSE):
            result = generate_daily_report(
                base_dir=data_dir,
                output_dir=output_dir,
                date="2026-07-26",
                issue=1,
            )

        assert result is not None
        assert os.path.exists(result)
        assert result.endswith("2026-07-26.mdx")

        content = open(result, "r", encoding="utf-8").read()
        assert "零域日报 No.1" in content
        assert "友宝完成C轮融资" in content

    def test_no_data_returns_none(self, data_dir, tmp_path):
        output_dir = str(tmp_path / "output")
        result = generate_daily_report(
            base_dir=data_dir,
            output_dir=output_dir,
            date="2020-01-01",
        )
        assert result is None

    def test_uses_largest_published_issue(self, data_dir, tmp_path):
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "old.mdx").write_text(
            "---\ntitle: Old\nissue: 7\n---\n", encoding="utf-8"
        )

        with patch("generators.daily_report.call_llm", return_value=MOCK_LLM_RESPONSE):
            result = generate_daily_report(
                base_dir=data_dir,
                output_dir=str(tmp_path / "output"),
                date="2026-07-26",
                history_dir=str(history_dir),
            )

        assert "No.8" in open(result, "r", encoding="utf-8").read()

    def test_rejects_duplicate_published_headline(self, data_dir, tmp_path):
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        parsed = parse_llm_response(MOCK_LLM_RESPONSE)
        title = parsed.get("wechat_title", "")
        if not title:
            parsed["wechat_title"] = "Repeated headline"
            response = yaml.safe_dump(parsed, allow_unicode=True)
        else:
            response = MOCK_LLM_RESPONSE
        published_title = parsed.get("wechat_title", "Repeated headline")
        (history_dir / "old.mdx").write_text(
            f"---\ntitle: {published_title!r}\nissue: 4\n---\n",
            encoding="utf-8",
        )

        with patch("generators.daily_report.call_llm", return_value=response):
            with pytest.raises(DuplicateDailyReportError):
                generate_daily_report(
                    base_dir=data_dir,
                    output_dir=str(tmp_path / "output"),
                    date="2026-07-26",
                    history_dir=str(history_dir),
                )

    def test_filters_previously_published_source_urls(self, data_dir, tmp_path):
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "old.mdx").write_text(
            "---\n"
            "title: Old\n"
            "issue: 4\n"
            "sections:\n"
            "  - items:\n"
            "      - source_url: https://36kr.com/p/1?utm_source=daily\n"
            "---\n",
            encoding="utf-8",
        )

        with patch(
            "generators.daily_report.call_llm", return_value=MOCK_LLM_RESPONSE
        ) as call:
            generate_daily_report(
                base_dir=data_dir,
                output_dir=str(tmp_path / "output"),
                date="2026-07-26",
                history_dir=str(history_dir),
            )

        assert call.call_args.args[1] == 1
        assert published_source_urls(str(history_dir)) == {"https://36kr.com/p/1"}


class TestOperatorReportQualityGate:
    @staticmethod
    def valid_report():
        return {
            "wechat_title": "新品进入即时零售，智能柜先看动销率",
            "sections": [
                {
                    "level": "core",
                    "title": "新品进入即时零售渠道",
                    "excerpt": "某品牌开始通过即时零售销售新品。",
                    "insight": "运营商应先检查同类SKU的动销率和毛利，不宜直接扩品。",
                    "source_url": "https://example.com/direct-story",
                    "source_name": "示例来源",
                },
                {
                    "level": "support",
                    "title": "渠道补充信号",
                    "excerpt": "相关渠道扩大覆盖。",
                    "source_url": "https://example.com/support",
                    "source_name": "示例来源",
                },
            ],
            "decision": {
                "operators": {
                    "evidence": "某品牌开始通过即时零售销售新品。",
                    "metric": "同类SKU七日动销率",
                    "action": "先检查同类SKU，再决定是否扩品。",
                    "sample": "10台柜观察7天",
                    "kpi": "缺货率不升且毛利贡献改善",
                    "stop_condition": "缺货率上升则恢复原陈列",
                }
            },
        }

    def test_rejects_materially_similar_recent_headline(self, tmp_path):
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        (history_dir / "old.mdx").write_text(
            "---\n"
            "title: '【零域日报】12000家新华书店入驻闪购，AI Agent开始替你下单'\n"
            "issue: 4\n"
            "---\n",
            encoding="utf-8",
        )

        duplicate = find_duplicate_headline(
            {
                "wechat_title": (
                    "新华书店12000家门店入驻闪购，"
                    "即时零售进入品类扩张深水区"
                )
            },
            str(history_dir),
        )

        assert duplicate == str(history_dir / "old.mdx")

    def test_rejects_missing_direct_source_url(self):
        report = self.valid_report()
        report["sections"][1]["source_url"] = ""

        with pytest.raises(GeneratedReportQualityError, match="direct HTTP"):
            validate_generated_report(report)

    def test_rejects_more_than_one_core_story(self):
        report = self.valid_report()
        report["sections"][1]["level"] = "core"

        with pytest.raises(GeneratedReportQualityError, match="exactly one core"):
            validate_generated_report(report)

    def test_rejects_more_than_two_supporting_signals(self):
        report = self.valid_report()
        report["sections"].extend(
            [
                {
                    "level": "support",
                    "title": f"补充信号{index}",
                    "excerpt": "补充信息。",
                    "source_url": f"https://example.com/support-{index}",
                    "source_name": "示例来源",
                }
                for index in range(2, 4)
            ]
        )

        with pytest.raises(GeneratedReportQualityError, match="at most two"):
            validate_generated_report(report)

    def test_rejects_core_story_without_operating_metric(self):
        report = self.valid_report()
        report["sections"][0]["insight"] = "这件事值得行业持续关注。"

        with pytest.raises(GeneratedReportQualityError, match="operating metric"):
            validate_generated_report(report)

    def test_rejects_roundup_style_title(self):
        report = self.valid_report()
        report["wechat_title"] = "【零域日报】新品进入即时零售"

        with pytest.raises(GeneratedReportQualityError, match="roundup"):
            validate_generated_report(report)

    def test_rejects_missing_reversible_test_contract(self):
        report = self.valid_report()
        del report["decision"]["operators"]["stop_condition"]

        with pytest.raises(GeneratedReportQualityError, match="decision"):
            validate_generated_report(report)

    def test_accepts_one_actionable_core_story_and_two_or_fewer_signals(self):
        validate_generated_report(self.valid_report())


class TestEditorialPromptV11:
    def test_requires_operator_first_title_and_rejects_roundup_branding(self):
        prompt = _compose_system_prompt()

        assert "标题不得使用“日报”" in prompt
        assert "不使用期号" in prompt
        assert "回复柜机数量" in prompt

    def test_requires_one_metric_and_reversible_test_in_output_contract(self):
        template = _load_output_template()

        assert "metric" in template
        assert "sample" in template
        assert "stop_condition" in template


class TestFormatMaterialsEnriched:
    def test_includes_all_metadata(self):
        items = [{
            "source": "36kr_rss",
            "title": "友宝融资",
            "summary": "友宝完成融资",
            "url": "https://example.com",
            "metadata": {
                "boost_level": "star",
                "boost_score": 15,
                "boost_matched": ["core:无人零售"],
                "quality_score": 85,
                "ner": {
                    "entities": [{"text": "友宝", "type": "company", "confidence": 95}],
                    "events": [{"type": "financing", "subject": "友宝", "action": "完成融资", "object": "", "confidence": 90}],
                    "topics": ["无人零售"],
                },
            },
        }]
        materials = format_materials(items)
        assert "⭐" in materials
        assert "质量分: 85/100" in materials
        assert "友宝(company)" in materials
        assert "友宝完成融资" in materials
