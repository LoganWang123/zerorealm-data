"""Durable content candidate store + config loader."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from content.models import ContentCandidate, touch_timestamps
from utils.helpers import now_iso

DEFAULT_CONFIG_PATH = Path("config/content_pipeline.yaml")
DEFAULT_CANDIDATES_PATH = Path("data/state/content_candidates.json")


def load_content_config(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    if not target.is_file():
        return {
            "timezone": "Asia/Shanghai",
            "freshness": {"daily_primary_window": "48h", "insight_window": "30d"},
            "daily": {"max_primary_signals": 1},
            "insight": {"require_theme_consistency": True},
            "paths": {
                "knowledge": "data/state/knowledge_store.json",
                "candidates": str(DEFAULT_CANDIDATES_PATH),
                "editorial_log": "data/state/editorial_review_log.jsonl",
                "packages": "data/state/publish_ready_packages.json",
                "review_drafts": "dist/review/content",
            },
        }
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def parse_window_to_hours(window: str | None) -> float | None:
    if not window:
        return None
    raw = str(window).strip().lower()
    if raw in {"none", "null", "unlimited"}:
        return None
    try:
        if raw.endswith("h"):
            return float(raw[:-1])
        if raw.endswith("d"):
            return float(raw[:-1]) * 24.0
        return float(raw)
    except ValueError:
        return None


class ContentCandidateStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_CANDIDATES_PATH
        self._by_id: dict[str, ContentCandidate] = {}

    def upsert(self, candidate: ContentCandidate) -> ContentCandidate:
        touch_timestamps(candidate)
        self._by_id[candidate.content_candidate_id] = candidate
        return candidate

    def get(self, candidate_id: str) -> ContentCandidate | None:
        return self._by_id.get(candidate_id)

    def all(self) -> list[ContentCandidate]:
        return list(self._by_id.values())

    def load(self, path: str | Path | None = None) -> int:
        target = Path(path) if path else self.path
        self.path = target
        if not target.exists():
            return 0
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        rows = payload.get("candidates") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return 0
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = ContentCandidate.from_dict(row)
            if not item.content_candidate_id:
                continue
            self._by_id[item.content_candidate_id] = item
            count += 1
        return count

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": now_iso(),
            "candidates": [c.to_dict() for c in self.all()],
        }
        fd, tmp_name = tempfile.mkstemp(
            prefix="content_candidates_", suffix=".json", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @classmethod
    def load_or_create(cls, path: str | Path | None = None) -> ContentCandidateStore:
        store = cls(path=path)
        store.load()
        return store
