from pathlib import Path


def test_daily_workflow_runs_three_mornings_and_uses_enabled_sources() -> None:
    workflow = Path(".github/workflows/daily-crawl.yaml").read_text(encoding="utf-8")

    assert "cron: '0 22 * * 0,2,4'" in workflow
    assert "--source " not in workflow
    assert "timeout-minutes: 180" in workflow
