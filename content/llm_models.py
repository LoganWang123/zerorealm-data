"""DeepSeek / LLM model identity and legacy fail-fast helpers."""

from __future__ import annotations

import os

LEGACY_DEEPSEEK_MODELS = frozenset({"deepseek-chat", "deepseek-reasoner"})
SUPPORTED_DEEPSEEK_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro"})
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class LLMConfigError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(f"{self.code}: {self.message}")


def resolve_llm_api_key(env: dict[str, str] | None = None) -> str:
    """Canonical secret is LLM_API_KEY; DEEPSEEK_API_KEY is compatibility fallback only."""
    source = env if env is not None else os.environ
    return str(source.get("LLM_API_KEY") or source.get("DEEPSEEK_API_KEY") or "").strip()


def assert_supported_model(model: str) -> str:
    name = (model or "").strip()
    if name in LEGACY_DEEPSEEK_MODELS:
        raise LLMConfigError(
            "DEEPSEEK_LEGACY_MODEL",
            f"Model '{name}' is retired. Use deepseek-v4-flash (default) or deepseek-v4-pro.",
        )
    return name


def normalize_deepseek_base_url(base_url: str | None) -> str:
    url = (base_url or DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    # Official docs accept https://api.deepseek.com; OpenAI SDK often wants /v1.
    if url.endswith("/v1"):
        return url
    if "api.deepseek.com" in url:
        return f"{url}/v1"
    return url
