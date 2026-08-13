"""Detect slim vs legacy daily-crawl.yaml.

The slim Daily Collection workflow is the live shape. Keep this helper so
runtime GHA-safety tests can still describe both forms.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/daily-crawl.yaml")


def load_daily_workflow() -> tuple[dict, str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict)
    return loaded, text


def is_new_collection_workflow(workflow: dict, text: str) -> bool:
    jobs = workflow.get("jobs") or {}
    return "collect" in jobs and "contract-check" in jobs
