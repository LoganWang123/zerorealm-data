"""Cost Tracker — LLM token / cost accounting.

Records every LLM call's token usage and cost.
M2: in-memory + JSON file export.
M3+: migrate to PostgreSQL (evaluation_runs / evaluation_cases).
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

from utils.helpers import CST

# Pricing table (CNY per million tokens, approximate)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 17.5, "output": 70.0},
    "gpt-4o-mini": {"input": 1.05, "output": 4.2},
    "deepseek-chat": {"input": 1.0, "output": 2.0},
    "deepseek-reasoner": {"input": 4.0, "output": 16.0},
    "qwen-plus": {"input": 0.8, "output": 2.0},
    "qwen-max": {"input": 2.0, "output": 6.0},
    "qwen-turbo": {"input": 0.3, "output": 0.6},
    "glm-4": {"input": 15.0, "output": 15.0},
    "glm-4-flash": {"input": 0.0, "output": 0.0},
}


@dataclass
class LLMCallRecord:
    """Single LLM call record."""

    task: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_cny: float
    latency_ms: int
    prompt_name: str | None = None
    prompt_version: int | None = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(CST).isoformat(timespec="seconds")


class CostTracker:
    """Accumulate LLM call costs.

    Usage::

        tracker = CostTracker()
        tracker.record("daily_report", "gpt-4o", 1200, 800, latency_ms=3200)
        print(tracker.summary())
        tracker.save_daily("logs")
    """

    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []
        self._total_cost: float = 0.0

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in CNY based on pricing table."""
        pricing = MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        input_cost = prompt_tokens / 1_000_000 * pricing["input"]
        output_cost = completion_tokens / 1_000_000 * pricing["output"]
        return round(input_cost + output_cost, 6)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        task: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int = 0,
        prompt_name: str | None = None,
        prompt_version: int | None = None,
    ) -> LLMCallRecord:
        """Record a single LLM call."""
        cost = self.estimate_cost(model, prompt_tokens, completion_tokens)
        rec = LLMCallRecord(
            task=task,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_cny=cost,
            latency_ms=latency_ms,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )
        self.records.append(rec)
        self._total_cost += cost
        return rec

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def total_calls(self) -> int:
        return len(self.records)

    def summary(self) -> dict:
        """Return a JSON-serialisable summary."""
        by_task: dict[str, int] = {}
        by_model: dict[str, int] = {}
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for r in self.records:
            by_task[r.task] = by_task.get(r.task, 0) + 1
            by_model[r.model] = by_model.get(r.model, 0) + 1
            total_prompt_tokens += r.prompt_tokens
            total_completion_tokens += r.completion_tokens

        return {
            "total_calls": self.total_calls,
            "total_cost_cny": round(self._total_cost, 4),
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "by_task": by_task,
            "by_model": by_model,
            "date": datetime.now(CST).strftime("%Y-%m-%d"),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_daily(self, log_dir: str = "logs") -> str:
        """Write today's cost summary to ``{log_dir}/cost_{date}.json``."""
        os.makedirs(log_dir, exist_ok=True)
        date_str = datetime.now(CST).strftime("%Y%m%d")
        path = os.path.join(log_dir, f"cost_{date_str}.json")

        data = {
            "summary": self.summary(),
            "records": [
                {
                    "task": r.task,
                    "model": r.model,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "cost_cny": r.cost_cny,
                    "latency_ms": r.latency_ms,
                    "prompt_name": r.prompt_name,
                    "timestamp": r.timestamp,
                }
                for r in self.records
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path
