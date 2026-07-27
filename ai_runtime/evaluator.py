"""Evaluation Hook — sample LLM calls for offline evaluation.

Aligned with Execution Architecture §5.6:
- Not every call is evaluated, only sampled (default 5%)
- Samples written to evaluation_cases (M2: JSON file, M3+: PostgreSQL)
- Periodic evaluation_runs aggregate results

Usage::

    from ai_runtime.evaluator import EvaluationHook

    hook = EvaluationHook(sample_rate=0.05)
    hook.maybe_record(response, input_text="...")
"""

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime

from utils.helpers import CST


@dataclass
class EvalCase:
    """A single evaluation case (sampled LLM call)."""

    task: str
    model: str
    input_text: str
    output_text: str
    prompt_name: str | None = None
    prompt_version: int | None = None
    latency_ms: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(CST).isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "model": self.model,
            "input": self.input_text[:2000],  # truncate for storage
            "output": self.output_text[:2000],
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }


class EvaluationHook:
    """Sample LLM calls and persist for offline evaluation.

    Parameters
    ----------
    sample_rate:
        Fraction of calls to record (0.0 ~ 1.0). Default 5%.
    output_dir:
        Directory for evaluation case files.
    """

    def __init__(
        self,
        sample_rate: float = 0.05,
        output_dir: str = "logs/eval",
    ) -> None:
        self.sample_rate = sample_rate
        self.output_dir = output_dir
        self._cases: list[EvalCase] = []

    def should_sample(self) -> bool:
        """Decide whether to sample this call."""
        return random.random() < self.sample_rate

    def maybe_record(
        self,
        response,
        input_text: str = "",
    ) -> bool:
        """Conditionally record an LLM response for evaluation.

        Parameters
        ----------
        response:
            An ``LLMResponse`` instance.
        input_text:
            The user prompt sent to the model.

        Returns True if the call was sampled and recorded.
        """
        if not self.should_sample():
            return False

        case = EvalCase(
            task=response.task,
            model=response.model,
            input_text=input_text,
            output_text=response.content,
            prompt_name=response.prompt_name,
            prompt_version=response.prompt_version,
            latency_ms=response.latency_ms,
        )
        self._cases.append(case)
        return True

    @property
    def recorded_count(self) -> int:
        return len(self._cases)

    def flush(self) -> str | None:
        """Write accumulated cases to a JSON file. Returns path or None."""
        if not self._cases:
            return None

        os.makedirs(self.output_dir, exist_ok=True)
        date_str = datetime.now(CST).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.output_dir, f"eval_cases_{date_str}.json")

        data = {
            "count": len(self._cases),
            "cases": [c.to_dict() for c in self._cases],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._cases.clear()
        return path

    def summary(self) -> dict:
        """Return summary of sampled cases in memory."""
        by_task: dict[str, int] = {}
        for c in self._cases:
            by_task[c.task] = by_task.get(c.task, 0) + 1
        return {
            "recorded": len(self._cases),
            "sample_rate": self.sample_rate,
            "by_task": by_task,
        }
