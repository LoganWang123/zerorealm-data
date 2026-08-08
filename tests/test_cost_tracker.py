"""Tests for ai_runtime/cost_tracker.py — token / cost accounting."""

import json
import os

import pytest

from ai_runtime.cost_tracker import CostTracker, MODEL_PRICING


class TestEstimateCost:
    def test_known_model(self):
        cost = CostTracker.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        expected = MODEL_PRICING["gpt-4o-mini"]["input"] + MODEL_PRICING["gpt-4o-mini"]["output"]
        assert abs(cost - expected) < 0.01

    def test_unknown_model_zero(self):
        assert CostTracker.estimate_cost("unknown-model", 1000, 1000) == 0.0

    def test_zero_tokens(self):
        assert CostTracker.estimate_cost("gpt-4o", 0, 0) == 0.0

    def test_proportional(self):
        small = CostTracker.estimate_cost("deepseek-v4-flash", 1000, 1000)
        large = CostTracker.estimate_cost("deepseek-v4-flash", 2000, 2000)
        assert abs(large - small * 2) < 1e-6

    def test_v4_models_priced(self):
        assert CostTracker.estimate_cost("deepseek-v4-flash", 1_000_000, 0) > 0
        assert CostTracker.estimate_cost("deepseek-v4-pro", 1_000_000, 0) > CostTracker.estimate_cost(
            "deepseek-v4-flash", 1_000_000, 0
        )


class TestCostTracker:
    def test_record_and_total(self):
        tracker = CostTracker()
        tracker.record("task_a", "gpt-4o-mini", 1000, 500, latency_ms=200)
        assert tracker.total_calls == 1
        assert tracker.total_cost > 0

    def test_multiple_records_accumulate(self):
        tracker = CostTracker()
        tracker.record("a", "gpt-4o-mini", 100, 100)
        tracker.record("b", "gpt-4o-mini", 100, 100)
        assert tracker.total_calls == 2

    def test_summary_structure(self):
        tracker = CostTracker()
        tracker.record("daily", "gpt-4o", 500, 300, latency_ms=100)
        tracker.record("ner", "qwen-plus", 200, 100, latency_ms=50)

        s = tracker.summary()
        assert s["total_calls"] == 2
        assert "total_cost_cny" in s
        assert s["by_task"]["daily"] == 1
        assert s["by_task"]["ner"] == 1
        assert s["by_model"]["gpt-4o"] == 1
        assert s["total_prompt_tokens"] == 700
        assert s["total_completion_tokens"] == 400

    def test_save_daily(self, tmp_path):
        tracker = CostTracker()
        tracker.record("test", "gpt-4o-mini", 100, 50)
        path = tracker.save_daily(str(tmp_path))

        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["summary"]["total_calls"] == 1
        assert len(data["records"]) == 1
        assert data["records"][0]["task"] == "test"

    def test_record_returns_record(self):
        tracker = CostTracker()
        rec = tracker.record("x", "gpt-4o", 10, 5, latency_ms=42)
        assert rec.task == "x"
        assert rec.latency_ms == 42
        assert rec.timestamp != ""
