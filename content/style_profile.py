"""ZeroRealm editorial style profile loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

STYLE_PATH = Path(__file__).resolve().parent.parent / "config" / "editorial_style.yaml"


@dataclass
class StyleProfile:
    version: int
    language: str
    tone: list[str] = field(default_factory=list)
    preferred: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    ai_style_patterns: list[str] = field(default_factory=list)
    opening_forbid_patterns: list[str] = field(default_factory=list)
    closing_forbid_patterns: list[str] = field(default_factory=list)
    daily: dict = field(default_factory=dict)
    insight: dict = field(default_factory=dict)
    golden_benchmark: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(self.raw)


def load_style_profile(path: Path | None = None) -> StyleProfile:
    p = path or STYLE_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return StyleProfile(
        version=int(data.get("version") or 1),
        language=str(data.get("language") or "zh-CN"),
        tone=list(data.get("tone") or []),
        preferred=list(data.get("preferred") or []),
        avoid=list(data.get("avoid") or []),
        ai_style_patterns=list(data.get("ai_style_patterns") or []),
        opening_forbid_patterns=list(data.get("opening_forbid_patterns") or []),
        closing_forbid_patterns=list(data.get("closing_forbid_patterns") or []),
        daily=dict(data.get("daily") or {}),
        insight=dict(data.get("insight") or {}),
        golden_benchmark=dict(data.get("golden_benchmark") or {}),
        raw=dict(data),
    )
