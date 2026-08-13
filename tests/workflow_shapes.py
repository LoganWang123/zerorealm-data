"""Detect slim vs legacy daily-crawl.yaml without failing the suite on either.

TODO: After the GitHub PAT has ``workflow`` scope, push the slim Daily
Collection workflow and remove the legacy branches from contract tests.
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
