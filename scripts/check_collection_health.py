"""Judge latest crawl metrics for the daily collection health gate.

Success: at least one enabled source succeeded.
Fail: no metrics file, unreadable metrics, or sources_success < 1.

Offline by design — tests must not need the network.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def find_latest_metrics(logs_dir: Path) -> Path | None:
    if not logs_dir.is_dir():
        return None
    files = [path for path in logs_dir.glob("*_metrics.json") if path.is_file()]
    if not files:
        return None
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0]


def load_metrics(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("metrics payload must be a JSON object")
    return payload


def evaluate_collection_health(payload: dict | None) -> tuple[bool, str]:
    if payload is None:
        return False, "no metrics"
    raw_success = payload.get("sources_success", 0)
    try:
        sources_success = int(raw_success)
    except (TypeError, ValueError):
        return False, "invalid sources_success"
    if sources_success >= 1:
        return True, "at least one enabled source succeeded"
    return False, "all sources failed or none succeeded"


def render_summary(payload: dict | None, *, ok: bool, reason: str) -> str:
    lines = [
        "## Daily collection health",
        "",
        f"- result: {'success' if ok else 'fail'}",
        f"- reason: {reason}",
    ]
    if payload is None:
        lines.extend(
            [
                "- sources_success: n/a",
                "- sources_failed: n/a",
                "- items_new: n/a",
                "- errors: no metrics file",
            ]
        )
    else:
        errors = payload.get("errors") or []
        if not isinstance(errors, list):
            errors = [errors]
        shown = errors[:20]
        extra = len(errors) - len(shown)
        error_text = json.dumps(shown, ensure_ascii=False)
        if extra > 0:
            error_text += f" (+{extra} more)"
        lines.extend(
            [
                f"- sources_success: {payload.get('sources_success', 0)}",
                f"- sources_failed: {payload.get('sources_failed', 0)}",
                f"- items_new: {payload.get('items_new', 0)}",
                f"- errors: {error_text}",
            ]
        )
    return "\n".join(lines) + "\n"


def write_summary(text: str, summary_path: Path | None) -> None:
    print(text, end="")
    if summary_path is None:
        return
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def resolve_summary_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if env_path:
        return Path(env_path)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, default=Path("logs"))
    parser.add_argument("--metrics", type=Path, default=None)
    parser.add_argument("--summary-path", type=Path, default=None)
    args = parser.parse_args(argv)

    summary_path = resolve_summary_path(args.summary_path)
    metrics_path = args.metrics
    if metrics_path is None:
        metrics_path = find_latest_metrics(args.logs_dir)

    payload: dict | None = None
    if metrics_path is None or not metrics_path.is_file():
        ok, reason = evaluate_collection_health(None)
        write_summary(render_summary(None, ok=ok, reason=reason), summary_path)
        return 1

    try:
        payload = load_metrics(metrics_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        text = render_summary(None, ok=False, reason=f"invalid metrics: {exc}")
        write_summary(text, summary_path)
        return 1

    ok, reason = evaluate_collection_health(payload)
    write_summary(render_summary(payload, ok=ok, reason=reason), summary_path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
