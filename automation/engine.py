"""Workflow Engine — execute automation workflows with policy gates.

Aligned with Execution Architecture §1.2 (Automation Context):
- Event-driven trigger matching
- Sequential step execution with retry
- Policy gate (auto / approval / dry_run)
- Action recording + rollback hooks

Usage::

    from automation.engine import WorkflowEngine

    engine = WorkflowEngine()
    engine.create_workflow("alert_notify", trigger_event="alert", steps=[...])
    results = engine.emit_event("alert", {"level": "critical", ...})
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Callable

from automation import (
    Workflow,
    WorkflowStep,
    ActionRecord,
    generate_workflow_id,
    generate_action_id,
)
from utils.helpers import CST
from utils.logger import get_logger


# ---------------------------------------------------------------------------
# Built-in Action Executors
# ---------------------------------------------------------------------------


def action_log(payload: dict, config: dict) -> dict:
    """Log action — write to structured log."""
    logger = get_logger()
    message = config.get("message", "Workflow action triggered")
    logger.info("[automation] %s | payload=%s", message, json.dumps(payload, ensure_ascii=False)[:200])
    return {"logged": True, "message": message}


def action_notify(payload: dict, config: dict) -> dict:
    """Notify action — console/notification output."""
    logger = get_logger()
    channel = config.get("channel", "console")
    title = payload.get("title", "Notification")
    message = payload.get("message", "")

    if channel == "console":
        logger.info("[notify] %s: %s", title, message)

    return {"notified": True, "channel": channel, "title": title}


def action_enrich(payload: dict, config: dict) -> dict:
    """Enrich action — add metadata to payload (placeholder for future KB enrichment)."""
    fields = config.get("add_fields", {})
    enriched = {**payload, **fields}
    return {"enriched": True, "fields_added": list(fields.keys())}


def action_webhook(payload: dict, config: dict) -> dict:
    """Webhook action — POST to external URL (dry-run in M6, real in M7+)."""
    url = config.get("url", "")
    if not url:
        return {"sent": False, "error": "no url configured"}

    # M6: dry-run only (no actual HTTP call to avoid side effects)
    return {"sent": False, "dry_run": True, "url": url}


def action_publish(payload: dict, config: dict) -> dict:
    """Publish action — trigger content publishing (delegates to publish.py)."""
    channel = config.get("channel", "wechat")
    date = payload.get("date", "")
    return {"published": False, "channel": channel, "date": date, "deferred": True}


# Action registry
ACTION_EXECUTORS: dict[str, Callable[[dict, dict], dict]] = {
    "log": action_log,
    "notify": action_notify,
    "enrich": action_enrich,
    "webhook": action_webhook,
    "publish": action_publish,
}


# ---------------------------------------------------------------------------
# Workflow Engine
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Execute workflows triggered by domain events.

    Usage::

        engine = WorkflowEngine("data/automation/workflows.json")
        engine.create_workflow(
            "alert_notify",
            trigger_event="alert",
            steps=[
                {"name": "log_alert", "action_type": "log", "config": {"message": "Alert!"}},
                {"name": "notify_user", "action_type": "notify", "config": {"channel": "console"}},
            ],
        )
        results = engine.emit_event("alert", {"title": "友宝融资", "level": "critical"})
    """

    def __init__(self, persist_path: str = "data/automation/workflows.json") -> None:
        self.persist_path = persist_path
        self.logger = get_logger()
        self._workflows: dict[str, Workflow] = {}
        self._action_log: list[ActionRecord] = []
        self._load()

    # ------------------------------------------------------------------
    # Workflow Management
    # ------------------------------------------------------------------

    def create_workflow(
        self,
        name: str,
        trigger_event: str = "",
        trigger_condition: dict | None = None,
        steps: list[dict] | None = None,
        policy: str = "auto",
    ) -> Workflow:
        """Create and register a new workflow."""
        wf_id = generate_workflow_id(name)

        if wf_id in self._workflows:
            return self._workflows[wf_id]

        condition = trigger_condition or {}
        if trigger_event:
            condition["event_type"] = trigger_event

        workflow_steps = []
        for s in (steps or []):
            workflow_steps.append(WorkflowStep(
                name=s["name"],
                action_type=s.get("action_type", "log"),
                config=s.get("config", {}),
                condition=s.get("condition", ""),
                retry_count=s.get("retry_count", 0),
                timeout_seconds=s.get("timeout_seconds", 30),
            ))

        wf = Workflow(
            id=wf_id,
            name=name,
            trigger_type="event" if trigger_event else "manual",
            trigger_condition=condition,
            steps=workflow_steps,
            policy=policy,
        )
        self._workflows[wf_id] = wf
        self.logger.info("[automation] Workflow created: %s (%s)", name, wf_id)
        return wf

    def remove_workflow(self, name: str) -> bool:
        wf_id = generate_workflow_id(name)
        if wf_id in self._workflows:
            del self._workflows[wf_id]
            return True
        return False

    def pause_workflow(self, name: str) -> bool:
        wf_id = generate_workflow_id(name)
        wf = self._workflows.get(wf_id)
        if wf:
            wf.status = "paused"
            return True
        return False

    def resume_workflow(self, name: str) -> bool:
        wf_id = generate_workflow_id(name)
        wf = self._workflows.get(wf_id)
        if wf:
            wf.status = "active"
            return True
        return False

    def list_workflows(self, status: str | None = None) -> list[Workflow]:
        wfs = list(self._workflows.values())
        if status:
            wfs = [w for w in wfs if w.status == status]
        return wfs

    # ------------------------------------------------------------------
    # Event Emission & Execution
    # ------------------------------------------------------------------

    def emit_event(self, event_type: str, context: dict | None = None) -> list[ActionRecord]:
        """Emit a domain event, triggering all matching workflows.

        Returns list of action records from all triggered workflows.
        """
        context = context or {}
        all_records: list[ActionRecord] = []

        for wf in self._workflows.values():
            if wf.matches_trigger(event_type, context):
                records = self._execute_workflow(wf, context)
                all_records.extend(records)

        if all_records:
            self.logger.info(
                "[automation] Event '%s' triggered %d actions across workflows",
                event_type, len(all_records),
            )

        return all_records

    def run_manual(self, workflow_name: str, context: dict | None = None) -> list[ActionRecord]:
        """Manually trigger a workflow by name."""
        wf_id = generate_workflow_id(workflow_name)
        wf = self._workflows.get(wf_id)
        if not wf:
            self.logger.warning("[automation] Workflow '%s' not found", workflow_name)
            return []
        return self._execute_workflow(wf, context or {})

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_workflow(self, wf: Workflow, context: dict) -> list[ActionRecord]:
        """Execute all steps in a workflow sequentially."""
        # Policy gate
        if wf.policy == "dry_run":
            self.logger.info("[automation] Workflow '%s' in dry_run mode, skipping", wf.name)
            return []

        if wf.policy == "approval":
            self.logger.info("[automation] Workflow '%s' requires approval, recording only", wf.name)
            # Record pending actions but don't execute
            records = []
            for i, step in enumerate(wf.steps):
                record = ActionRecord(
                    id=generate_action_id(wf.id, step.name, wf.run_count),
                    workflow_id=wf.id,
                    step_name=step.name,
                    action_type=step.action_type,
                    status="pending",
                    payload=context,
                )
                records.append(record)
                self._action_log.append(record)
            return records

        # Auto-execute
        records: list[ActionRecord] = []
        wf.record_run()

        for i, step in enumerate(wf.steps):
            record = self._execute_step(wf, step, i, context)
            records.append(record)
            self._action_log.append(record)

            # Stop on failure (no continue-on-error in M6)
            if record.status == "failed":
                self.logger.warning(
                    "[automation] Step '%s' failed in workflow '%s': %s",
                    step.name, wf.name, record.error,
                )
                break

        return records

    def _execute_step(
        self, wf: Workflow, step: WorkflowStep, index: int, context: dict,
    ) -> ActionRecord:
        """Execute a single workflow step with retry."""
        record = ActionRecord(
            id=generate_action_id(wf.id, step.name, wf.run_count),
            workflow_id=wf.id,
            step_name=step.name,
            action_type=step.action_type,
            status="running",
            payload=context,
            started_at=datetime.now(CST).isoformat(timespec="seconds"),
        )

        executor = ACTION_EXECUTORS.get(step.action_type)
        if not executor:
            record.status = "failed"
            record.error = f"Unknown action type: {step.action_type}"
            record.finished_at = datetime.now(CST).isoformat(timespec="seconds")
            return record

        # Retry loop
        max_attempts = step.retry_count + 1
        for attempt in range(max_attempts):
            try:
                start = time.time()
                result = executor(context, step.config)
                record.duration_ms = int((time.time() - start) * 1000)
                record.result = result
                record.status = "completed"
                record.finished_at = datetime.now(CST).isoformat(timespec="seconds")
                return record
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    continue
                record.status = "failed"
                record.error = str(e)
                record.finished_at = datetime.now(CST).isoformat(timespec="seconds")
                return record

        return record

    # ------------------------------------------------------------------
    # Action Log
    # ------------------------------------------------------------------

    def get_action_log(self, workflow_id: str | None = None, limit: int = 50) -> list[ActionRecord]:
        records = self._action_log
        if workflow_id:
            records = [r for r in records if r.workflow_id == workflow_id]
        return records[-limit:]

    @property
    def action_count(self) -> int:
        return len(self._action_log)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> str | None:
        try:
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
            data = {
                "version": 1,
                "workflows": [w.to_dict() for w in self._workflows.values()],
                "action_log": [a.to_dict() for a in self._action_log[-200:]],
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return self.persist_path
        except Exception as e:
            self.logger.warning("[automation] Save failed: %s", e)
            return None

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for w in data.get("workflows", []):
                steps = [
                    WorkflowStep(
                        name=s["name"],
                        action_type=s.get("action_type", "log"),
                        config=s.get("config", {}),
                        condition=s.get("condition", ""),
                        retry_count=s.get("retry_count", 0),
                        timeout_seconds=s.get("timeout_seconds", 30),
                    )
                    for s in w.get("steps", [])
                ]
                wf = Workflow(
                    id=w["id"], name=w["name"],
                    trigger_type=w.get("trigger_type", "event"),
                    trigger_condition=w.get("trigger_condition", {}),
                    steps=steps,
                    policy=w.get("policy", "auto"),
                    status=w.get("status", "active"),
                    run_count=w.get("run_count", 0),
                    last_run_at=w.get("last_run_at", ""),
                    created_at=w.get("created_at", ""),
                )
                self._workflows[wf.id] = wf
            self.logger.info("[automation] Loaded %d workflows", len(self._workflows))
        except Exception as e:
            self.logger.warning("[automation] Load failed: %s", e)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        active = sum(1 for w in self._workflows.values() if w.is_active)
        completed = sum(1 for a in self._action_log if a.status == "completed")
        failed = sum(1 for a in self._action_log if a.status == "failed")
        return {
            "total_workflows": len(self._workflows),
            "active_workflows": active,
            "total_actions": len(self._action_log),
            "completed_actions": completed,
            "failed_actions": failed,
        }
