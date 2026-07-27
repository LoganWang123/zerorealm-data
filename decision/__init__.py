"""Decision Context — domain models.

Aligned with Execution Architecture §1.2 (Decision Context):
- WatchRule: monitoring configuration for entities/events
- Alert: triggered notification when conditions are met
- Decision: AI-generated recommendation with reasoning trace

M6+: migrate to Supabase watch_rules / decisions / actions tables.
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


class RuleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DecisionStatus(str, Enum):
    GENERATED = "generated"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# WatchRule
# ---------------------------------------------------------------------------


@dataclass
class WatchRule:
    """A monitoring rule that watches for specific events on entities.

    Aligned with Execution Architecture §2.7 (watch_rules table).
    """

    id: str
    name: str
    target_entities: list[str] = field(default_factory=list)   # entity IDs or names
    conditions: dict = field(default_factory=dict)             # {event_types: [], keywords: [], threshold: {}}
    priority: str = "medium"                                    # low / medium / high / critical
    notification: dict = field(default_factory=dict)           # {channel: "console", ...}
    status: str = "active"                                     # active / paused / archived
    last_triggered_at: str = ""
    trigger_count: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(CST).isoformat(timespec="seconds")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def matches_event(self, event_type: str, entities: list[str], text: str = "") -> bool:
        """Check if an event matches this rule's conditions."""
        if not self.is_active:
            return False

        # Check event type filter
        event_types = self.conditions.get("event_types", [])
        if event_types and event_type not in event_types:
            return False

        # Check entity filter
        if self.target_entities:
            entity_match = any(
                e.lower() in [t.lower() for t in self.target_entities]
                for e in entities
            )
            if not entity_match:
                return False

        # Check keyword filter
        keywords = self.conditions.get("keywords", [])
        if keywords and text:
            text_lower = text.lower()
            if not any(kw.lower() in text_lower for kw in keywords):
                return False

        return True

    def record_trigger(self) -> None:
        """Record that this rule was triggered."""
        self.trigger_count += 1
        self.last_triggered_at = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "target_entities": self.target_entities,
            "conditions": self.conditions,
            "priority": self.priority,
            "notification": self.notification,
            "status": self.status,
            "last_triggered_at": self.last_triggered_at,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------


@dataclass
class Alert:
    """A triggered alert from a WatchRule."""

    id: str
    rule_id: str
    rule_name: str
    level: str = "info"                     # info / warning / critical
    title: str = ""
    message: str = ""
    source_signal: str = ""                 # signal that triggered
    entities: list[str] = field(default_factory=list)
    event_type: str = ""
    acknowledged: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "source_signal": self.source_signal,
            "entities": self.entities,
            "event_type": self.event_type,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@dataclass
class ReasoningStep:
    """A single step in the reasoning trace."""

    step: int
    action: str
    result: str
    confidence: int = 50

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "action": self.action,
            "result": self.result,
            "confidence": self.confidence,
        }


@dataclass
class Decision:
    """An AI-generated decision/recommendation.

    Aligned with Execution Architecture §2.7 (decisions table).
    """

    id: str
    objective: str                                       # decision goal
    recommendation: str = ""                             # what to do
    confidence: int = 50                                 # 0-100
    reasoning_trace: list[ReasoningStep] = field(default_factory=list)
    policy_check: str = "pending"                        # passed / approval_required / rejected
    status: str = "generated"                            # generated / approved / executed / rejected
    context: dict = field(default_factory=dict)          # input context
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(CST).isoformat(timespec="seconds")

    @property
    def is_actionable(self) -> bool:
        """Can this decision be auto-executed?"""
        return (
            self.status == "generated"
            and self.policy_check == "passed"
            and self.confidence >= 90
        )

    def approve(self) -> None:
        self.status = "approved"
        self.policy_check = "passed"

    def reject(self) -> None:
        self.status = "rejected"
        self.policy_check = "rejected"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "objective": self.objective,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasoning_trace": [s.to_dict() for s in self.reasoning_trace],
            "policy_check": self.policy_check,
            "status": self.status,
            "context": self.context,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def generate_rule_id(name: str) -> str:
    """Deterministic rule ID from name."""
    return hashlib.sha256(f"rule:{name.lower().strip()}".encode()).hexdigest()[:16]


def generate_alert_id(rule_id: str, signal_id: str) -> str:
    """Deterministic alert ID."""
    return hashlib.sha256(f"alert:{rule_id}:{signal_id}".encode()).hexdigest()[:16]


def generate_decision_id(objective: str) -> str:
    """Deterministic decision ID."""
    key = f"decision:{objective.lower().strip()}:{datetime.now(CST).strftime('%Y%m%d')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
