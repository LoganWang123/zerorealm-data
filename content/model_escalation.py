"""Model escalation policy — disabled by default (no auto Pro spend)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelEscalationPolicy:
    enabled: bool = False
    flash_model: str = "deepseek-v4-flash"
    pro_model: str = "deepseek-v4-pro"
    escalate_on_quality_fail: bool = False
    auto_call_pro: bool = False

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "flash_model": self.flash_model,
            "pro_model": self.pro_model,
            "escalate_on_quality_fail": self.escalate_on_quality_fail,
            "auto_call_pro": self.auto_call_pro,
            "note": "Flash FAIL must not auto-call Pro. Human chooses escalation.",
        }


def default_escalation_policy() -> ModelEscalationPolicy:
    return ModelEscalationPolicy(enabled=False)
