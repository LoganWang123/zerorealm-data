"""Cloud daily-collection workflow: cron kept; no LLM / publish / secrets."""

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/daily-crawl.yaml")


def load_workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_has_schedule_cron_015_and_dispatch():
    workflow = load_workflow()
    on = workflow[True]
    assert "schedule" in on
    assert "workflow_dispatch" in on
    assert any(item.get("cron") == "0 15 * * *" for item in on["schedule"])


def test_workflow_runs_local_only_crawl_and_artifacts():
    workflow = load_workflow()
    text = WORKFLOW.read_text(encoding="utf-8")
    job = workflow["jobs"]["collect"]
    step_names = [step.get("name", "") for step in job["steps"]]

    assert job.get("timeout-minutes") == 90
    assert job.get("needs") in (None, [], "")
    assert "Collection health gate and summary" in step_names
    assert "Crawl local-only (no LLM / no remote store)" in step_names
    assert "Upload crawl artifacts" in step_names
    assert "python main.py --local-only --date" in text
    assert "data/state" in text
    assert "data/" in text and "logs/" in text
    assert "playwright install" not in text.lower()
    assert "install chromium" not in text.lower()
    collect_runs = "\n".join(
        step.get("run", "") for step in job["steps"] if isinstance(step.get("run"), str)
    )
    assert "pytest" not in collect_runs


def test_workflow_has_no_generate_publish_or_sensitive_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "generate_daily" not in text
    assert "publish.py" not in text
    assert "export_public_bundle" not in text
    assert "check_cross_channel_daily" not in text
    assert "${{ secrets." not in text
    assert "wechat_appid" not in lowered
    assert "wechat_secret" not in lowered
    assert "website_repo_token" not in lowered
    assert "deepseek" not in lowered
    assert "llm_api_key" not in lowered
    assert "supabase" not in lowered
    assert "agnes_api" not in lowered
