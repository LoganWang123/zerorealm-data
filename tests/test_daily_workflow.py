from pathlib import Path


def test_daily_workflow_runs_at_2300_shanghai_and_uses_enabled_sources() -> None:
    workflow = Path(".github/workflows/daily-crawl.yaml").read_text(encoding="utf-8")

    assert "cron: '0 15 * * *'" in workflow
    assert "--source " not in workflow
    assert "timeout-minutes: 180" in workflow
