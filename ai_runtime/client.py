"""Unified LLM Client — single entry point for all LLM calls.

Features:
- Retry with exponential backoff
- Fallback model chain
- Automatic cost tracking
- Lineage metadata on every response

Usage::

    client = LLMClient()
    resp = client.chat(
        task="daily_report",
        system="You are ...",
        user="Generate ...",
    )
    print(resp.content)
    print(resp.lineage())
"""

import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

from ai_runtime.cost_tracker import CostTracker
from ai_runtime.evaluator import EvaluationHook
from utils.logger import get_logger

# Shared singletons (per process)
_global_tracker = CostTracker()
_global_eval_hook = EvaluationHook(sample_rate=0.05)


def get_cost_tracker() -> CostTracker:
    """Return the process-wide CostTracker instance."""
    return _global_tracker


def get_eval_hook() -> EvaluationHook:
    """Return the process-wide EvaluationHook instance."""
    return _global_eval_hook


@dataclass
class LLMResponse:
    """Standardised LLM response with lineage metadata."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    task: str = ""
    prompt_name: str | None = None
    prompt_version: int | None = None

    def lineage(self) -> dict:
        """Return lineage metadata (aligned with Execution Architecture §6)."""
        return {
            "operator": "model",
            "model": self.model,
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_cny": CostTracker.estimate_cost(
                self.model, self.prompt_tokens, self.completion_tokens
            ),
        }


class LLMClient:
    """Unified LLM client wrapping any OpenAI-compatible API.

    Parameters
    ----------
    api_key / base_url / model:
        Override env vars ``LLM_API_KEY``, ``LLM_BASE_URL``, ``LLM_MODEL``.
    fallback_models:
        Ordered list tried when the primary model fails.
    max_retries:
        Per-model retry count (exponential backoff 1 s → 2 s → 4 s …).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        max_retries: int = 2,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "LLM_BASE_URL", "https://api.openai.com/v1"
        )
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.fallback_models = fallback_models or []
        self.max_retries = max_retries
        self.timeout = timeout
        self.tracker = _global_tracker
        self.eval_hook = _global_eval_hook
        self.logger = get_logger()

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def chat(
        self,
        task: str,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        prompt_name: str | None = None,
        prompt_version: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request with retry + fallback."""
        models_to_try = [model or self.model] + self.fallback_models
        last_error: Exception | None = None

        for current_model in models_to_try:
            for attempt in range(self.max_retries):
                try:
                    return self._call(
                        task=task,
                        system=system,
                        user=user,
                        model=current_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        prompt_name=prompt_name,
                        prompt_version=prompt_version,
                    )
                except Exception as e:
                    last_error = e
                    wait = 2**attempt
                    self.logger.warning(
                        "[llm] %s/%s attempt %d failed: %s, retry in %ds",
                        task,
                        current_model,
                        attempt + 1,
                        e,
                        wait,
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(wait)

            self.logger.warning("[llm] Model %s exhausted, trying fallback", current_model)

        raise RuntimeError(
            f"All LLM models failed for task '{task}': {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call(
        self,
        task: str,
        system: str,
        user: str,
        model: str,
        temperature: float,
        max_tokens: int | None,
        prompt_name: str | None,
        prompt_version: int | None,
    ) -> LLMResponse:
        start = time.time()

        kwargs: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = self._client.chat.completions.create(**kwargs)
        latency_ms = int((time.time() - start) * 1000)

        content = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        # Track cost
        self.tracker.record(
            task=task,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )

        self.logger.info(
            "[llm] task=%s model=%s tokens=%d+%d latency=%dms",
            task,
            model,
            prompt_tokens,
            completion_tokens,
            latency_ms,
        )

        # Evaluation sampling (§5.6)
        self.eval_hook.maybe_record(
            LLMResponse(
                content=content, model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms, task=task,
                prompt_name=prompt_name,
                prompt_version=prompt_version,
            ),
            input_text=user[:1000],
        )

        return LLMResponse(
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            task=task,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )
