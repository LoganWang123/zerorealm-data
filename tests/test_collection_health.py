"""Offline tests for collection health gate and main.py system-exit contract."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import main as main_mod
from crawlers.base import RawItem
from scripts.check_collection_health import (
    evaluate_collection_health,
    find_latest_metrics,
    main as health_main,
    render_summary,
)


ROOT = Path(__file__).resolve().parents[1]
HEALTH_SCRIPT = ROOT / "scripts" / "check_collection_health.py"


def _write_metrics(path: Path, **fields) -> Path:
    payload = {
        "run_id": "test",
        "sources_success": 0,
        "sources_failed": 0,
        "items_new": 0,
        "errors": [],
    }
    payload.update(fields)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_item(source: str = "ok_rss") -> RawItem:
    return RawItem(
        id="item1",
        source=source,
        source_type="rss",
        language="zh-CN",
        title="友宝智能柜补货效率提升",
        url=f"https://example.com/{source}",
        published_at="2026-08-13T08:00:00+08:00",
        crawled_at="2026-08-13T09:00:00+08:00",
        run_id="test_health",
        crawl_status="success",
        http_status=200,
        content_html="<p>补货</p>",
        content_text="友宝智能柜补货效率提升，缺货率下降。",
        summary="智能柜补货效率提升",
        author="test",
        tags=["智能柜"],
        metadata={"score": 80},
    )


def test_health_passes_when_one_source_succeeds_even_if_others_fail(tmp_path):
    metrics = {
        "sources_success": 1,
        "sources_failed": 4,
        "items_new": 3,
        "errors": ["js_spa: browser missing"],
    }
    ok, reason = evaluate_collection_health(metrics)
    assert ok is True
    assert "at least one" in reason

    metrics_path = _write_metrics(tmp_path / "run_metrics.json", **metrics)
    summary = tmp_path / "summary.md"
    assert (
        health_main(
            [
                "--metrics",
                str(metrics_path),
                "--summary-path",
                str(summary),
            ]
        )
        == 0
    )
    text = summary.read_text(encoding="utf-8")
    assert "sources_success: 1" in text
    assert "sources_failed: 4" in text
    assert "items_new: 3" in text
    assert "js_spa: browser missing" in text
    assert "result: success" in text


def test_health_fails_when_all_sources_fail_or_metrics_missing(tmp_path):
    ok, _reason = evaluate_collection_health(
        {"sources_success": 0, "sources_failed": 3, "items_new": 0, "errors": ["a", "b"]}
    )
    assert ok is False

    all_fail = _write_metrics(
        tmp_path / "all_fail_metrics.json",
        sources_success=0,
        sources_failed=2,
        items_new=0,
        errors=["rss: timeout", "web: 403"],
    )
    summary = tmp_path / "summary.md"
    assert health_main(["--metrics", str(all_fail), "--summary-path", str(summary)]) == 1
    text = summary.read_text(encoding="utf-8")
    assert "result: fail" in text
    assert "sources_success: 0" in text
    assert "sources_failed: 2" in text

    empty_dir = tmp_path / "no-logs"
    empty_dir.mkdir()
    missing_summary = tmp_path / "missing.md"
    assert (
        health_main(
            ["--logs-dir", str(empty_dir), "--summary-path", str(missing_summary)]
        )
        == 1
    )
    missing_text = missing_summary.read_text(encoding="utf-8")
    assert "no metrics" in missing_text
    assert "sources_success: n/a" in missing_text


def test_health_cli_picks_latest_metrics_without_network(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    _write_metrics(logs / "old_metrics.json", sources_success=0, sources_failed=1)
    newer = logs / "new_metrics.json"
    _write_metrics(newer, sources_success=2, sources_failed=1, items_new=9)
    newer_stat = newer.stat()
    # Ensure mtime ordering if the FS timestamp granularity is coarse.
    import os

    os.utime(newer, (newer_stat.st_atime + 5, newer_stat.st_mtime + 5))
    assert find_latest_metrics(logs) == newer
    summary = tmp_path / "out.md"
    assert health_main(["--logs-dir", str(logs), "--summary-path", str(summary)]) == 0
    assert "sources_success: 2" in summary.read_text(encoding="utf-8")


def test_health_script_subprocess_is_offline(tmp_path):
    metrics = _write_metrics(tmp_path / "ok_metrics.json", sources_success=1, items_new=2)
    result = subprocess.run(
        [
            sys.executable,
            str(HEALTH_SCRIPT),
            "--metrics",
            str(metrics),
            "--summary-path",
            str(tmp_path / "s.md"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "sources_success: 1" in result.stdout


def test_render_summary_includes_required_fields():
    text = render_summary(
        {
            "sources_success": 3,
            "sources_failed": 1,
            "items_new": 12,
            "errors": ["x"],
        },
        ok=True,
        reason="at least one enabled source succeeded",
    )
    assert "sources_success: 3" in text
    assert "sources_failed: 1" in text
    assert "items_new: 12" in text
    assert "errors:" in text


def test_main_returns_nonzero_on_system_exception(monkeypatch):
    def boom():
        raise RuntimeError("config exploded")

    monkeypatch.setattr(main_mod, "load_config", boom)
    assert main_mod.main(["--local-only"]) == 1


def test_main_returns_zero_when_one_source_fails(monkeypatch, tmp_path):
    class OkCrawler:
        async def run(self):
            return [_make_item()]

    class BoomCrawler:
        async def run(self):
            raise RuntimeError("source down")

    sources = [
        {"id": "ok_rss", "enabled": True, "type": "rss"},
        {"id": "bad_web", "enabled": True, "type": "web"},
    ]
    settings = {
        "output": {"base_dir": str(tmp_path / "data")},
        "logging": {"dir": str(tmp_path / "logs")},
        "digest": {"priority_sources": []},
        "quality": {},
        "dedup": {},
    }

    def fake_get_crawler(cfg, _run_id):
        return OkCrawler() if cfg["id"] == "ok_rss" else BoomCrawler()

    monkeypatch.setattr(main_mod, "load_config", lambda: (sources, settings))
    monkeypatch.setattr(main_mod, "setup_logger", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_mod, "generate_run_id", lambda: "health_mixed")
    monkeypatch.setattr(main_mod, "get_crawler", fake_get_crawler)

    assert main_mod.main(["--local-only", "--date", "2026-08-13"]) == 0
    metrics_path = tmp_path / "logs" / "health_mixed_metrics.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["sources_success"] == 1
    assert payload["sources_failed"] == 1
    assert any("bad_web" in err for err in payload["errors"])
    assert health_main(["--metrics", str(metrics_path)]) == 0


def test_system_exception_exits_nonzero_and_still_writes_metrics(monkeypatch, tmp_path):
    class OkCrawler:
        async def run(self):
            return [_make_item()]

    sources = [{"id": "ok_rss", "enabled": True, "type": "rss"}]
    settings = {
        "output": {"base_dir": str(tmp_path / "data")},
        "logging": {"dir": str(tmp_path / "logs")},
        "digest": {"priority_sources": []},
        "quality": {},
        "dedup": {},
    }

    def boom(*_args, **_kwargs):
        raise RuntimeError("dedup exploded")

    monkeypatch.setattr(main_mod, "get_crawler", lambda cfg, run_id: OkCrawler())
    monkeypatch.setattr(main_mod, "filter_duplicates", boom)
    monkeypatch.setattr(main_mod, "load_config", lambda: (sources, settings))
    monkeypatch.setattr(main_mod, "setup_logger", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_mod, "generate_run_id", lambda: "sys_fail")

    assert main_mod.main(["--local-only", "--date", "2026-08-13"]) == 1
    payload = json.loads((tmp_path / "logs" / "sys_fail_metrics.json").read_text(encoding="utf-8"))
    assert any("system: dedup exploded" in err for err in payload["errors"])


def test_all_sources_fail_main_exits_zero_but_health_gate_fails(monkeypatch, tmp_path):
    class BoomCrawler:
        async def run(self):
            raise RuntimeError("down")

    sources = [{"id": "a", "enabled": True, "type": "rss"}]
    settings = {
        "output": {"base_dir": str(tmp_path / "data")},
        "logging": {"dir": str(tmp_path / "logs")},
        "digest": {"priority_sources": []},
        "quality": {},
        "dedup": {},
    }
    monkeypatch.setattr(main_mod, "get_crawler", lambda cfg, run_id: BoomCrawler())
    metrics = asyncio.run(
        main_mod.crawl_all(
            sources,
            settings,
            run_id="all_fail",
            local_only=True,
            output_date="2026-08-13",
        )
    )
    assert metrics["sources_success"] == 0
    assert metrics["sources_failed"] == 1
    assert health_main(["--metrics", str(tmp_path / "logs" / "all_fail_metrics.json")]) == 1
