"""Prompt Registry — YAML-based prompt template management.

M2: file-based (config/prompts/*.yaml), versioned by filename suffix.
M3+: migrate to prompt_registry table in PostgreSQL.

Prompt file format::

    name: daily_report
    version: 1
    description: "Generate daily industry report"
    model: gpt-4o-mini
    temperature: 0.3
    max_tokens: 4000
    system: |
      You are ...
    user: |
      Here are {count} items ...
"""

import os
import re
from dataclasses import dataclass, field

import yaml


@dataclass
class PromptTemplate:
    """A versioned prompt template."""

    name: str
    version: int
    system: str
    user: str
    description: str = ""
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    variables: list[str] = field(default_factory=list)

    def render(self, **kwargs) -> tuple[str, str]:
        """Fill variables, return ``(system_text, user_text)``."""
        system = self.system.format(**kwargs) if kwargs else self.system
        user = self.user.format(**kwargs) if kwargs else self.user
        return system, user

    def render_safe(self, **kwargs) -> tuple[str, str]:
        """Render with ``{var}`` left intact when variable is missing."""

        def _safe(text: str) -> str:
            for key, value in kwargs.items():
                text = text.replace(f"{{{key}}}", str(value))
            return text

        return _safe(self.system), _safe(self.user)


class PromptRegistry:
    """Load and manage prompt templates from a directory.

    Usage::

        registry = PromptRegistry("config/prompts")
        tpl = registry.get("daily_report")
        system, user = tpl.render(count=42, issue=1, date="2026-07-26", materials="...")
    """

    def __init__(self, prompt_dir: str | None = None) -> None:
        if prompt_dir is None:
            prompt_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "config", "prompts"
            )
        self.prompt_dir = prompt_dir
        self._cache: dict[str, PromptTemplate] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_all()

    def _load_all(self) -> None:
        """Scan ``prompt_dir`` for ``*.yaml`` / ``*.yml`` files."""
        self._cache.clear()
        if not os.path.isdir(self.prompt_dir):
            self._loaded = True
            return

        for filename in sorted(os.listdir(self.prompt_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            filepath = os.path.join(self.prompt_dir, filename)
            try:
                tpl = self._parse_file(filepath)
                if tpl:
                    self._cache[tpl.name] = tpl
            except Exception:
                # Skip malformed prompt files silently in M2
                pass

        self._loaded = True

    @staticmethod
    def _parse_file(filepath: str) -> PromptTemplate | None:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or "name" not in data:
            return None

        system = data.get("system", "")
        user = data.get("user", "")

        # Auto-detect ``{var}`` placeholders
        variables = sorted(set(re.findall(r"\{(\w+)\}", system + user)))

        return PromptTemplate(
            name=data["name"],
            version=data.get("version", 1),
            system=system,
            user=user,
            description=data.get("description", ""),
            model=data.get("model"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            variables=variables,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str) -> PromptTemplate | None:
        """Return the active template for *name*, or ``None``."""
        self._ensure_loaded()
        return self._cache.get(name)

    def render(self, prompt_name: str, **kwargs) -> tuple[str, str]:
        """Shortcut: load + render. Raises ``KeyError`` if not found."""
        tpl = self.get(prompt_name)
        if tpl is None:
            raise KeyError(f"Prompt '{prompt_name}' not found in {self.prompt_dir}")
        return tpl.render(**kwargs)

    def list_prompts(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._cache.keys())

    def reload(self) -> None:
        """Force re-scan of the prompt directory."""
        self._loaded = False
        self._ensure_loaded()
