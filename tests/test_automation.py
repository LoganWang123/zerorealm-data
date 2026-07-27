"""Tests for automation/ — Workflow, WorkflowEngine, built-in actions."""

import pytest

from automation import (
    Workflow,
    WorkflowStep,
    ActionRecord,
    generate_workflow_id,
    generate_action_id,
)
from automation.engine import (
    WorkflowEngine,
    action_log,
    action_notify,
    action_enrich,
    action_webhook,
    ACTION_EXECUTORS,
)


# ---------------------------------------------------------------------------
# Workflow model
# ---------------------------------------------------------------------------


class TestWorkflow:
    def test_matches_trigger_event(self):
        wf = Workflow(
            id="w1", name="test",
            trigger_type="event",
            trigger_condition={"event_type": "alert"},
        )
        assert wf.matches_trigger("alert") is True
        assert wf.matches_trigger("signal") is False

    def test_matches_trigger_with_context(self):
        wf = Workflow(
            id="w1", name="test",
            trigger_type="event",
            trigger_condition={"event_type": "alert", "match": {"level": "critical"}},
        )
        assert wf.matches_trigger("alert", {"level": "critical"}) is True
        assert wf.matches_trigger("alert", {"level": "info"}) is False

    def test_paused_workflow_no_trigger(self):
        wf = Workflow(id="w1", name="test", trigger_type="event",
                      trigger_condition={"event_type": "alert"}, status="paused")
        assert wf.matches_trigger("alert") is False

    def test_manual_workflow_no_event_trigger(self):
        wf = Workflow(id="w1", name="test", trigger_type="manual")
        assert wf.matches_trigger("alert") is False

    def test_record_run(self):
        wf = Workflow(id="w1", name="test")
        wf.record_run()
        assert wf.run_count == 1
        assert wf.last_run_at != ""


# ---------------------------------------------------------------------------
# Built-in Actions
# ---------------------------------------------------------------------------


class TestBuiltInActions:
    def test_action_log(self):
        result = action_log({"title": "test"}, {"message": "hello"})
        assert result["logged"] is True

    def test_action_notify(self):
        result = action_notify({"title": "Alert", "message": "msg"}, {"channel": "console"})
        assert result["notified"] is True
        assert result["channel"] == "console"

    def test_action_enrich(self):
        result = action_enrich({"title": "x"}, {"add_fields": {"source": "auto"}})
        assert result["enriched"] is True
        assert "source" in result["fields_added"]

    def test_action_webhook_no_url(self):
        result = action_webhook({}, {})
        assert result["sent"] is False

    def test_action_webhook_dry_run(self):
        result = action_webhook({}, {"url": "https://example.com/hook"})
        assert result["dry_run"] is True

    def test_registry_complete(self):
        assert "log" in ACTION_EXECUTORS
        assert "notify" in ACTION_EXECUTORS
        assert "enrich" in ACTION_EXECUTORS
        assert "webhook" in ACTION_EXECUTORS
        assert "publish" in ACTION_EXECUTORS


# ---------------------------------------------------------------------------
# WorkflowEngine
# ---------------------------------------------------------------------------


class TestWorkflowEngine:
    @pytest.fixture
    def engine(self, tmp_path):
        return WorkflowEngine(persist_path=str(tmp_path / "wf.json"))

    def test_create_workflow(self, engine):
        wf = engine.create_workflow(
            "alert_notify",
            trigger_event="alert",
            steps=[{"name": "log_it", "action_type": "log", "config": {"message": "Alert!"}}],
        )
        assert wf.name == "alert_notify"
        assert len(engine.list_workflows()) == 1

    def test_create_duplicate(self, engine):
        engine.create_workflow("wf1", trigger_event="alert")
        engine.create_workflow("wf1", trigger_event="alert")
        assert len(engine.list_workflows()) == 1

    def test_remove_workflow(self, engine):
        engine.create_workflow("wf1", trigger_event="alert")
        assert engine.remove_workflow("wf1") is True
        assert len(engine.list_workflows()) == 0

    def test_pause_resume(self, engine):
        engine.create_workflow("wf1", trigger_event="alert")
        engine.pause_workflow("wf1")
        assert engine.list_workflows()[0].status == "paused"
        engine.resume_workflow("wf1")
        assert engine.list_workflows()[0].status == "active"

    def test_emit_event_triggers_workflow(self, engine):
        engine.create_workflow(
            "alert_handler",
            trigger_event="alert",
            steps=[
                {"name": "log_step", "action_type": "log", "config": {"message": "got alert"}},
                {"name": "notify_step", "action_type": "notify", "config": {"channel": "console"}},
            ],
        )
        records = engine.emit_event("alert", {"title": "友宝融资", "level": "critical"})
        assert len(records) == 2
        assert all(r.status == "completed" for r in records)

    def test_emit_event_no_match(self, engine):
        engine.create_workflow("alert_handler", trigger_event="alert")
        records = engine.emit_event("signal", {})
        assert len(records) == 0

    def test_dry_run_policy(self, engine):
        engine.create_workflow(
            "dry_wf", trigger_event="alert",
            steps=[{"name": "s1", "action_type": "log"}],
            policy="dry_run",
        )
        records = engine.emit_event("alert", {})
        assert len(records) == 0

    def test_approval_policy(self, engine):
        engine.create_workflow(
            "approval_wf", trigger_event="alert",
            steps=[{"name": "s1", "action_type": "notify"}],
            policy="approval",
        )
        records = engine.emit_event("alert", {})
        assert len(records) == 1
        assert records[0].status == "pending"

    def test_run_manual(self, engine):
        engine.create_workflow(
            "manual_wf", trigger_event="",
            steps=[{"name": "s1", "action_type": "log", "config": {"message": "manual"}}],
        )
        records = engine.run_manual("manual_wf", {"data": "test"})
        assert len(records) == 1
        assert records[0].status == "completed"

    def test_run_manual_not_found(self, engine):
        records = engine.run_manual("nonexistent")
        assert records == []

    def test_unknown_action_type_fails(self, engine):
        engine.create_workflow(
            "bad_wf", trigger_event="alert",
            steps=[{"name": "s1", "action_type": "nonexistent_action"}],
        )
        records = engine.emit_event("alert", {})
        assert len(records) == 1
        assert records[0].status == "failed"
        assert "Unknown action type" in records[0].error

    def test_stops_on_failure(self, engine):
        engine.create_workflow(
            "fail_wf", trigger_event="alert",
            steps=[
                {"name": "bad", "action_type": "nonexistent"},
                {"name": "good", "action_type": "log"},
            ],
        )
        records = engine.emit_event("alert", {})
        assert len(records) == 1  # stopped after first failure
        assert records[0].status == "failed"

    def test_action_log(self, engine):
        engine.create_workflow("wf", trigger_event="x", steps=[{"name": "s", "action_type": "log"}])
        engine.emit_event("x", {})
        engine.emit_event("x", {})
        assert engine.action_count == 2

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "wf.json")
        e1 = WorkflowEngine(persist_path=path)
        e1.create_workflow("wf1", trigger_event="alert", steps=[{"name": "s1", "action_type": "log"}])
        e1.emit_event("alert", {})
        e1.save()

        e2 = WorkflowEngine(persist_path=path)
        assert len(e2.list_workflows()) == 1
        assert e2.list_workflows()[0].name == "wf1"

    def test_stats(self, engine):
        engine.create_workflow("wf1", trigger_event="a", steps=[{"name": "s", "action_type": "log"}])
        engine.create_workflow("wf2", trigger_event="b")
        engine.pause_workflow("wf2")
        engine.emit_event("a", {})
        stats = engine.stats()
        assert stats["total_workflows"] == 2
        assert stats["active_workflows"] == 1
        assert stats["completed_actions"] == 1


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


class TestIdGeneration:
    def test_workflow_id_deterministic(self):
        assert generate_workflow_id("test") == generate_workflow_id("test")

    def test_action_id_unique_per_run(self):
        id1 = generate_action_id("w1", "step1", 0)
        id2 = generate_action_id("w1", "step1", 1)
        assert id1 != id2
