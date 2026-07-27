"""Automation Context — domain models.

Aligned with Execution Architecture §1.2 (Automation Context):
- Workflow: event-triggered action sequence with policy gate
- Action: single executable step within a workflow

M6+: migrate to Supabase actions table.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from utils.helpers import CST


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkflowStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class TriggerType(str, Enum):
    EVENT = "event"           # domain event (e.g. alert triggered)
    CRON = "cron"             # scheduled
    MANUAL = "manual"         # human-triggered
    WEBHOOK = "webhook"       # external HTTP call


class PolicyMode(str, Enum):
    AUTO = "auto"                       # execute immediately
    APPROVAL_REQUIRED = "approval"      # needs human approval
    DRY_RUN = "dry_run"                 # simulate only


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStep:
    """A single step definition within a workflow."""

    name: str
    action_type: str              # notify / log / enrich / publish / webhook
    config: dict = field(default_factory=dict)
    condition: str = ""           # optional: only run if condition met
    retry_count: int = 0
    timeout_seconds: int = 30

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "action_type": self.action_type,
            "config": self.config,
            "condition": self.condition,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class Workflow:
    """An event-triggered automation workflow.

    Aligned with Execution Architecture §2.7 (actions table).
    """

    id: str
    name: str
    trigger_type: str = "event"                    # event / cron / manual / webhook
    trigger_condition: dict = field(default_factory=dict)  # {event_type: "alert", ...}
    steps: list[WorkflowStep] = field(default_factory=list)
    policy: str = "auto"                           # auto / approval / dry_run
    status: str = "active"                         # active / paused / archived
    run_count: int = 0
    last_run_at: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(CST).isoformat(timespec="seconds")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def matches_trigger(self, event_type: str, context: dict | None = None) -> bool:
        """Check if this workflow should be triggered by an event."""
        if not self.is_active:
            return False
        if self.trigger_type != "event":
            return False

        expected = self.trigger_condition.get("event_type", "")
        if expected and expected != event_type:
            return False

        # Optional: match on context fields
        match_fields = self.trigger_condition.get("match", {})
        if match_fields and context:
            for key, value in match_fields.items():
                if context.get(key) != value:
                    return False

        return True

    def record_run(self) -> None:
        self.run_count += 1
        self.last_run_at = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger_condition": self.trigger_condition,
            "steps": [s.to_dict() for s in self.steps],
            "policy": self.policy,
            "status": self.status,
            "run_count": self.run_count,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Action (execution record)
# ---------------------------------------------------------------------------


@dataclass
class ActionRecord:
    """Record of a single action execution.

    Aligned with Execution Architecture §2.7 (actions table).
    """

    id: str
    workflow_id: str
    step_name: str
    action_type: str
    status: str = "pending"          # pending / running / completed / failed / skipped / rolled_back
    payload: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    error: str = ""
    feedback: str = ""               # correct / incorrect / partial (human feedback)
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "step_name": self.step_name,
            "action_type": self.action_type,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "feedback": self.feedback,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def generate_workflow_id(name: str) -> str:
    return hashlib.sha256(f"workflow:{name.lower().strip()}".encode()).hexdigest()[:16]


def generate_action_id(workflow_id: str, step_name: str, run_index: int) -> str:
    key = f"action:{workflow_id}:{step_name}:{run_index}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
