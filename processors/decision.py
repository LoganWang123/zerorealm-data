"""Decision Processor — watch rules evaluation + alert generation.

Bridges Knowledge/NER events → Decision Context (WatchRule → Alert → Decision).

Pipeline position: after NER/Knowledge, evaluates watch rules against new signals.

Usage::

    from processors.decision import DecisionEngine

    engine = DecisionEngine()
    engine.add_rule("watch_ubox", ["友宝"], {"event_types": ["financing", "cooperation"]})
    alerts = engine.evaluate_item(item)
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from crawlers.base import RawItem
from decision import (
    WatchRule,
    Alert,
    Decision,
    ReasoningStep,
    generate_rule_id,
    generate_alert_id,
    generate_decision_id,
)
from utils.helpers import CST
from utils.logger import get_logger


class DecisionEngine:
    """Evaluate watch rules against incoming signals and generate alerts.

    Usage::

        engine = DecisionEngine("data/decision/rules.json")
        engine.add_rule("watch_financing", ["友宝", "丰e足食"], {"event_types": ["financing"]})
        alerts = engine.evaluate_item(item)
        engine.save()
    """

    def __init__(self, persist_path: str = "data/decision/rules.json") -> None:
        self.persist_path = persist_path
        self.logger = get_logger()
        self._rules: dict[str, WatchRule] = {}
        self._alerts: list[Alert] = []
        self._load()

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(
        self,
        name: str,
        target_entities: list[str] | None = None,
        conditions: dict | None = None,
        priority: str = "medium",
        notification: dict | None = None,
    ) -> WatchRule:
        """Create and register a new watch rule."""
        rule_id = generate_rule_id(name)

        if rule_id in self._rules:
            return self._rules[rule_id]

        rule = WatchRule(
            id=rule_id,
            name=name,
            target_entities=target_entities or [],
            conditions=conditions or {},
            priority=priority,
            notification=notification or {"channel": "console"},
        )
        self._rules[rule_id] = rule
        self.logger.info("[decision] Rule added: %s (%s)", name, rule_id)
        return rule

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        rule_id = generate_rule_id(name)
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def pause_rule(self, name: str) -> bool:
        rule_id = generate_rule_id(name)
        rule = self._rules.get(rule_id)
        if rule:
            rule.status = "paused"
            return True
        return False

    def resume_rule(self, name: str) -> bool:
        rule_id = generate_rule_id(name)
        rule = self._rules.get(rule_id)
        if rule:
            rule.status = "active"
            return True
        return False

    def list_rules(self, status: str | None = None) -> list[WatchRule]:
        rules = list(self._rules.values())
        if status:
            rules = [r for r in rules if r.status == status]
        return rules

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_item(self, item: RawItem) -> list[Alert]:
        """Evaluate all active rules against a single item's NER data.

        Returns list of triggered alerts.
        """
        ner = item.metadata.get("ner", {})
        if not ner:
            return []

        entities = [e.get("text", "") for e in ner.get("entities", [])]
        events = ner.get("events", [])
        topics = ner.get("topics", [])
        text = f"{item.title} {item.summary}"

        triggered: list[Alert] = []

        for rule in self._rules.values():
            if not rule.is_active:
                continue

            # Check each event
            for event in events:
                event_type = event.get("type", "")
                event_entities = [event.get("subject", ""), event.get("object", "")]
                event_entities = [e for e in event_entities if e]

                if rule.matches_event(event_type, event_entities + entities, text):
                    alert = self._create_alert(rule, item, event_type, event_entities)
                    triggered.append(alert)
                    rule.record_trigger()
                    break  # one alert per rule per item
            else:
                # No event matched, check entity-only rules (no event_types filter)
                if not rule.conditions.get("event_types"):
                    if rule.matches_event("", entities, text):
                        alert = self._create_alert(rule, item, "mention", entities)
                        triggered.append(alert)
                        rule.record_trigger()

        if triggered:
            self._alerts.extend(triggered)
            self.logger.info(
                "[decision] %d alerts triggered for item %s",
                len(triggered), item.id,
            )

        return triggered

    def evaluate_batch(self, items: list[RawItem]) -> list[Alert]:
        """Evaluate rules against a batch of items."""
        all_alerts: list[Alert] = []
        for item in items:
            alerts = self.evaluate_item(item)
            all_alerts.extend(alerts)
        return all_alerts

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def get_alerts(self, acknowledged: bool | None = None) -> list[Alert]:
        alerts = self._alerts
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    @property
    def alert_count(self) -> int:
        return len(self._alerts)

    # ------------------------------------------------------------------
    # Decision Generation (rule-based, no LLM needed)
    # ------------------------------------------------------------------

    def generate_decision(self, objective: str, context: dict | None = None) -> Decision:
        """Generate a simple rule-based decision.

        For M6, this uses heuristics. M7+ can use LLM for reasoning.
        """
        decision_id = generate_decision_id(objective)

        # Simple heuristic: count relevant alerts and entities
        relevant_alerts = [
            a for a in self._alerts
            if not a.acknowledged and a.level in ("warning", "critical")
        ]

        steps = []
        confidence = 50

        if relevant_alerts:
            steps.append(ReasoningStep(
                step=1,
                action="Scan unacknowledged alerts",
                result=f"Found {len(relevant_alerts)} active alerts",
                confidence=80,
            ))
            confidence += min(len(relevant_alerts) * 10, 30)

        if context and context.get("entities"):
            steps.append(ReasoningStep(
                step=len(steps) + 1,
                action="Analyze entity context",
                result=f"{len(context['entities'])} entities in scope",
                confidence=70,
            ))
            confidence += 10

        steps.append(ReasoningStep(
            step=len(steps) + 1,
            action="Generate recommendation",
            result="Based on alert patterns and entity activity",
            confidence=confidence,
        ))

        # Policy check: high confidence → auto-pass
        policy = "passed" if confidence >= 80 else "approval_required"

        decision = Decision(
            id=decision_id,
            objective=objective,
            recommendation=f"Monitor {len(relevant_alerts)} active signals related to: {objective}",
            confidence=min(confidence, 100),
            reasoning_trace=steps,
            policy_check=policy,
            context=context or {},
        )

        return decision

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> str | None:
        try:
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
            data = {
                "version": 1,
                "rules": [r.to_dict() for r in self._rules.values()],
                "alerts": [a.to_dict() for a in self._alerts[-100:]],  # keep last 100
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return self.persist_path
        except Exception as e:
            self.logger.warning("[decision] Save failed: %s", e)
            return None

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for r in data.get("rules", []):
                rule = WatchRule(
                    id=r["id"], name=r["name"],
                    target_entities=r.get("target_entities", []),
                    conditions=r.get("conditions", {}),
                    priority=r.get("priority", "medium"),
                    notification=r.get("notification", {}),
                    status=r.get("status", "active"),
                    last_triggered_at=r.get("last_triggered_at", ""),
                    trigger_count=r.get("trigger_count", 0),
                    created_at=r.get("created_at", ""),
                )
                self._rules[rule.id] = rule
            for a in data.get("alerts", []):
                alert = Alert(
                    id=a["id"], rule_id=a["rule_id"],
                    rule_name=a.get("rule_name", ""),
                    level=a.get("level", "info"),
                    title=a.get("title", ""),
                    message=a.get("message", ""),
                    source_signal=a.get("source_signal", ""),
                    entities=a.get("entities", []),
                    event_type=a.get("event_type", ""),
                    acknowledged=a.get("acknowledged", False),
                    created_at=a.get("created_at", ""),
                )
                self._alerts.append(alert)
            self.logger.info(
                "[decision] Loaded %d rules, %d alerts",
                len(self._rules), len(self._alerts),
            )
        except Exception as e:
            self.logger.warning("[decision] Load failed: %s", e)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_alert(
        self, rule: WatchRule, item: RawItem, event_type: str, entities: list[str],
    ) -> Alert:
        alert_id = generate_alert_id(rule.id, item.id)

        # Determine level based on rule priority
        level_map = {"low": "info", "medium": "info", "high": "warning", "critical": "critical"}
        level = level_map.get(rule.priority, "info")

        return Alert(
            id=alert_id,
            rule_id=rule.id,
            rule_name=rule.name,
            level=level,
            title=f"[{rule.name}] {item.title[:50]}",
            message=f"Event: {event_type} | Entities: {', '.join(entities[:3])}",
            source_signal=item.id,
            entities=entities,
            event_type=event_type,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        active_rules = sum(1 for r in self._rules.values() if r.is_active)
        unacked = sum(1 for a in self._alerts if not a.acknowledged)
        return {
            "total_rules": len(self._rules),
            "active_rules": active_rules,
            "total_alerts": len(self._alerts),
            "unacknowledged_alerts": unacked,
        }
