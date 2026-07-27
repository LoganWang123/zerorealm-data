"""Tests for ai_runtime/prompt_registry.py — YAML prompt management."""

import os

import pytest

from ai_runtime.prompt_registry import PromptRegistry, PromptTemplate


@pytest.fixture
def prompt_dir(tmp_path):
    """Create a temp prompt directory with test templates."""
    d = tmp_path / "prompts"
    d.mkdir()

    (d / "test_prompt.yaml").write_text(
        """\
name: test_prompt
version: 2
description: "A test prompt"
model: gpt-4o-mini
temperature: 0.5
max_tokens: 1000
system: |
  You are a {role}.
user: |
  Hello {name}, today is {date}.
""",
        encoding="utf-8",
    )

    (d / "minimal.yaml").write_text(
        """\
name: minimal
version: 1
system: "Be helpful."
user: "Answer this."
""",
        encoding="utf-8",
    )

    # Malformed file — should be skipped
    (d / "broken.yaml").write_text("not: valid: yaml: [", encoding="utf-8")

    return str(d)


class TestPromptTemplate:
    def test_render(self):
        tpl = PromptTemplate(
            name="t", version=1,
            system="You are {role}.",
            user="Hi {name}.",
        )
        s, u = tpl.render(role="editor", name="Alice")
        assert s == "You are editor."
        assert u == "Hi Alice."

    def test_render_safe_missing_var(self):
        tpl = PromptTemplate(
            name="t", version=1,
            system="You are {role}.",
            user="Hi {name}, {missing}.",
        )
        s, u = tpl.render_safe(role="editor", name="Bob")
        assert s == "You are editor."
        assert "{missing}" in u  # left intact

    def test_variables_auto_detected(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        tpl = registry.get("test_prompt")
        assert set(tpl.variables) == {"role", "name", "date"}


class TestPromptRegistry:
    def test_get_existing(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        tpl = registry.get("test_prompt")
        assert tpl is not None
        assert tpl.name == "test_prompt"
        assert tpl.version == 2
        assert tpl.model == "gpt-4o-mini"
        assert tpl.temperature == 0.5
        assert tpl.max_tokens == 1000

    def test_get_minimal(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        tpl = registry.get("minimal")
        assert tpl is not None
        assert tpl.system == "Be helpful."

    def test_get_missing_returns_none(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        assert registry.get("nonexistent") is None

    def test_broken_file_skipped(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        # Should not crash, broken.yaml is skipped
        assert "broken" not in registry.list_prompts()

    def test_list_prompts(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        names = registry.list_prompts()
        assert "test_prompt" in names
        assert "minimal" in names

    def test_render_shortcut(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        s, u = registry.render("test_prompt", role="dev", name="X", date="2026")
        assert "dev" in s
        assert "X" in u

    def test_render_missing_raises(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        with pytest.raises(KeyError):
            registry.render("nonexistent")

    def test_empty_dir(self, tmp_path):
        empty = str(tmp_path / "empty")
        os.makedirs(empty, exist_ok=True)
        registry = PromptRegistry(empty)
        assert registry.list_prompts() == []

    def test_nonexistent_dir(self, tmp_path):
        registry = PromptRegistry(str(tmp_path / "nope"))
        assert registry.list_prompts() == []

    def test_reload(self, prompt_dir):
        registry = PromptRegistry(prompt_dir)
        assert registry.get("test_prompt") is not None
        registry.reload()
        assert registry.get("test_prompt") is not None
