"""Deterministic AI-style pattern detection for editorial warnings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from content.style_profile import StyleProfile, load_style_profile


@dataclass
class StyleWarning:
    code: str
    pattern: str
    count: int = 1
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "pattern": self.pattern,
            "count": self.count,
            "reason": self.reason,
        }


def _normalize_ellipsis_pattern(pat: str) -> str:
    # Convert human "随着……不断发展" into a loose regex.
    escaped = re.escape(pat)
    escaped = escaped.replace(re.escape("……"), ".{0,24}")
    escaped = escaped.replace(re.escape("..."), ".{0,24}")
    return escaped


def detect_ai_style_patterns(text: str, profile: StyleProfile | None = None) -> list[StyleWarning]:
    profile = profile or load_style_profile()
    body = text or ""
    warnings: list[StyleWarning] = []

    for pat in profile.ai_style_patterns:
        rx = re.compile(_normalize_ellipsis_pattern(pat))
        hits = list(rx.finditer(body))
        if hits:
            warnings.append(
                StyleWarning(
                    code="STYLE_PATTERN_WARNING",
                    pattern=pat,
                    count=len(hits),
                    reason="AI-template phrasing detected",
                )
            )

    # Structural smells
    not_but = len(re.findall(r"不是.{0,20}而是", body))
    if not_but >= 3:
        warnings.append(
            StyleWarning(
                code="STYLE_PATTERN_WARNING",
                pattern="不是A，而是B",
                count=not_but,
                reason="Overused contrast template",
            )
        )
    true_not = len(re.findall(r"真正.{0,20}不是.{0,20}而是", body))
    if true_not >= 2:
        warnings.append(
            StyleWarning(
                code="STYLE_PATTERN_WARNING",
                pattern="真正……不是……而是……",
                count=true_not,
                reason="Overused '真正…不是…而是…' template",
            )
        )

    # Mechanical numbered lists density
    numbered = len(re.findall(r"(?:^|\n)\s*[一二三四五六七八九十123456789][、.．]", body))
    if numbered >= 6:
        warnings.append(
            StyleWarning(
                code="STYLE_PATTERN_WARNING",
                pattern="mechanical_numbering",
                count=numbered,
                reason="Dense mechanical numbering",
            )
        )

    colon_count = body.count("：") + body.count(":")
    if colon_count >= 12:
        warnings.append(
            StyleWarning(
                code="STYLE_PATTERN_WARNING",
                pattern="excessive_colons",
                count=colon_count,
                reason="Too many colons",
            )
        )

    return warnings
