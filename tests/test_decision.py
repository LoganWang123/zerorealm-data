"""Tests for decision/ and processors/decision.py — WatchRule, Alert, DecisionEngine."""

import pytest

from crawlers.base import RawItem
from decision import (
    WatchRule,
    Alert,
    Decision,
    ReasoningStep,
    generate_rule_id,
    generate_alert_id,
)
from processors.decision import DecisionEngine


def _make_item(item_id: str, title: str, ner: dict | None = None) -> RawItem:
    return RawItem(
        id=item_id,
        source="36kr_rss",
        source_type="rss",
        language="zh-CN",
        title=title,
        url=f"https://example.com/{item_id}",
        published_at="2026-07-26T08:00:00+08:00",
        crawled_at="2026-07-26T09:00:00+08:00",
        run_id="test",
        crawl_status="success",
        http_status=200,
        content_html="",
        content_text="",
        summary=title,
        author="",
        metadata={"ner": ner} if ner else {},
    )


# ---------------------------------------------------------------------------
# WatchRule
# ---------------------------------------------------------------------------


class TestWatchRule:
    def test_matches_event_type(self):
        rule = WatchRule(
            id="r1", name="test",
            conditions={"event_types": ["financing"]},
        )
        assert rule.matches_event("financing", ["友宝"]) is True
        assert rule.matches_event("cooperation", ["友宝"]) is False

    def test_matches_entity_filter(self):
        rule = WatchRule(
            id="r1", name="test",
            target_entities=["友宝", "丰e足食"],
        )
        assert rule.matches_event("financing", ["友宝"]) is True
        assert rule.matches_event("financing", ["美团"]) is False

    def test_matches_keyword_filter(self):
        rule = WatchRule(
            id="r1", name="test",
            conditions={"keywords": ["融资", "IPO"]},
        )
        assert rule.matches_event("financing", [], text="友宝完成融资") is True
        assert rule.matches_event("financing", [], text="友宝发布新品") is False

    def test_paused_rule_no_match(self):
        rule = WatchRule(id="r1", name="test", status="paused")
        assert rule.matches_event("financing", ["友宝"]) is False

    def test_record_trigger(self):
        rule = WatchRule(id="r1", name="test")
        rule.record_trigger()
        assert rule.trigger_count == 1
        assert rule.last_triggered_at != ""


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


class TestDecision:
    def test_is_actionable(self):
        d = Decision(id="d1", objective="test", confidence=95, policy_check="passed")
        assert d.is_actionable is True

    def test_not_actionable_low_confidence(self):
        d = Decision(id="d1", objective="test", confidence=50, policy_check="passed")
        assert d.is_actionable is False

    def test_approve_reject(self):
        d = Decision(id="d1", objective="test")
        d.approve()
        assert d.status == "approved"
        d.reject()
        assert d.status == "rejected"


# ---------------------------------------------------------------------------
# DecisionEngine
# ---------------------------------------------------------------------------


class TestDecisionEngine:
    @pytest.fixture
    def engine(self, tmp_path):
        return DecisionEngine(persist_path=str(tmp_path / "rules.json"))

    def test_add_rule(self, engine):
        rule = engine.add_rule("watch_ubox", ["友宝"], {"event_types": ["financing"]})
        assert rule.name == "watch_ubox"
        assert len(engine.list_rules()) == 1

    def test_add_duplicate_rule(self, engine):
        engine.add_rule("watch_ubox", ["友宝"])
        engine.add_rule("watch_ubox", ["友宝"])
        assert len(engine.list_rules()) == 1

    def test_remove_rule(self, engine):
        engine.add_rule("watch_ubox", ["友宝"])
        assert engine.remove_rule("watch_ubox") is True
        assert len(engine.list_rules()) == 0

    def test_pause_resume(self, engine):
        engine.add_rule("watch_ubox", ["友宝"])
        engine.pause_rule("watch_ubox")
        assert engine.list_rules()[0].status == "paused"
        engine.resume_rule("watch_ubox")
        assert engine.list_rules()[0].status == "active"

    def test_evaluate_item_triggers_alert(self, engine):
        engine.add_rule("watch_financing", ["友宝"], {"event_types": ["financing"]})
        item = _make_item("sig1", "友宝完成C轮融资", ner={
            "entities": [{"text": "友宝", "type": "company", "confidence": 95}],
            "events": [{"type": "financing", "subject": "友宝", "action": "完成融资", "object": "", "confidence": 90}],
            "topics": [],
        })
        alerts = engine.evaluate_item(item)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "watch_financing"
        assert alerts[0].event_type == "financing"

    def test_evaluate_no_match(self, engine):
        engine.add_rule("watch_financing", ["友宝"], {"event_types": ["financing"]})
        item = _make_item("sig2", "元气森林发布新品", ner={
            "entities": [{"text": "元气森林", "type": "company", "confidence": 90}],
            "events": [{"type": "product_launch", "subject": "元气森林", "action": "发布新品", "object": "", "confidence": 85}],
            "topics": [],
        })
        alerts = engine.evaluate_item(item)
        assert len(alerts) == 0

    def test_evaluate_no_ner(self, engine):
        engine.add_rule("watch_all", [])
        item = _make_item("sig3", "无NER数据")
        alerts = engine.evaluate_item(item)
        assert len(alerts) == 0

    def test_entity_only_rule(self, engine):
        engine.add_rule("watch_ubox_mentions", ["友宝"])
        item = _make_item("sig4", "友宝新动态", ner={
            "entities": [{"text": "友宝", "type": "company", "confidence": 90}],
            "events": [],
            "topics": [],
        })
        alerts = engine.evaluate_item(item)
        assert len(alerts) == 1

    def test_evaluate_batch(self, engine):
        engine.add_rule("watch_financing", [], {"event_types": ["financing"]})
        items = [
            _make_item("s1", "友宝融资", ner={
                "entities": [{"text": "友宝", "type": "company", "confidence": 90}],
                "events": [{"type": "financing", "subject": "友宝", "action": "融资", "object": "", "confidence": 85}],
                "topics": [],
            }),
            _make_item("s2", "元气森林新品", ner={
                "entities": [{"text": "元气森林", "type": "company", "confidence": 90}],
                "events": [{"type": "product_launch", "subject": "元气森林", "action": "发布", "object": "", "confidence": 85}],
                "topics": [],
            }),
        ]
        alerts = engine.evaluate_batch(items)
        assert len(alerts) == 1

    def test_acknowledge_alert(self, engine):
        engine.add_rule("watch_all", [], {"event_types": ["financing"]})
        item = _make_item("s1", "融资", ner={
            "entities": [],
            "events": [{"type": "financing", "subject": "X", "action": "融资", "object": "", "confidence": 80}],
            "topics": [],
        })
        alerts = engine.evaluate_item(item)
        assert engine.acknowledge_alert(alerts[0].id) is True
        assert engine.get_alerts(acknowledged=True)[0].acknowledged is True

    def test_generate_decision(self, engine):
        decision = engine.generate_decision("扩大市场", {"entities": ["友宝"]})
        assert decision.objective == "扩大市场"
        assert decision.confidence > 0
        assert len(decision.reasoning_trace) > 0

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "rules.json")
        engine1 = DecisionEngine(persist_path=path)
        engine1.add_rule("watch_ubox", ["友宝"], {"event_types": ["financing"]})
        engine1.save()

        engine2 = DecisionEngine(persist_path=path)
        assert len(engine2.list_rules()) == 1
        assert engine2.list_rules()[0].name == "watch_ubox"

    def test_stats(self, engine):
        engine.add_rule("r1", ["友宝"])
        engine.add_rule("r2", ["美团"])
        engine.pause_rule("r2")
        stats = engine.stats()
        assert stats["total_rules"] == 2
        assert stats["active_rules"] == 1
