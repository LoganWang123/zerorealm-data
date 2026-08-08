"""LLMClient DeepSeek structured-output helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_runtime.client import LLMClient


def test_deepseek_json_disables_thinking(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            msg = SimpleNamespace(content='{"ok": true}', reasoning_content=None)
            choice = SimpleNamespace(message=msg)
            usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
            return SimpleNamespace(choices=[choice], usage=usage)

    client = LLMClient(api_key="test-key", base_url="https://api.deepseek.com", model="deepseek-v4-flash")
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client.tracker = MagicMock()
    client.eval_hook = MagicMock()
    client.logger = MagicMock()

    resp = client.chat(
        task="t",
        system="s",
        user="u",
        model="deepseek-v4-pro",
        response_format={"type": "json_object"},
        max_tokens=100,
    )
    assert resp.content == '{"ok": true}'
    assert captured.get("extra_body") == {"thinking": {"type": "disabled"}}
