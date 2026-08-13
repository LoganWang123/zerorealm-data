"""Offline smoke: daily collection workflow isolation and fault-tolerance contract."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/daily-crawl.yaml")


def load_workflow():
    text = WORKFLOW.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict)
    return loaded, text


def _job_runs(job: dict) -> str:
    return "\n".join(
        step.get("run", "") for step in job.get("steps", []) if isinstance(step.get("run"), str)
    )


def _step_by_name(job: dict, fragment: str) -> dict:
    for step in job.get("steps", []):
        if fragment in step.get("name", ""):
            return step
    raise AssertionError(f"step containing {fragment!r} not found")


def test_yaml_parses_and_keeps_cron_and_dispatch():
    workflow, _text = load_workflow()
    on = workflow[True]
    assert "workflow_dispatch" in on
    assert "schedule" in on
    assert any(item.get("cron") == "0 15 * * *" for item in on["schedule"])
    assert "date" in on["workflow_dispatch"]["inputs"]


def test_collect_does_not_depend_on_contract_check():
    workflow, _text = load_workflow()
    jobs = workflow["jobs"]
    assert "collect" in jobs
    assert "contract-check" in jobs
    collect = jobs["collect"]
    assert collect.get("needs") in (None, [], "")
    assert "needs" not in collect
    # Visible on the Actions UI, but must not skip collect or flip its verdict.
    assert jobs["contract-check"].get("continue-on-error") is True
    assert collect.get("continue-on-error") not in (True, "true")


def test_collect_has_no_full_pytest_or_playwright_browser():
    workflow, text = load_workflow()
    collect_runs = _job_runs(workflow["jobs"]["collect"])
    all_runs = "\n".join(
        _job_runs(job) for job in workflow["jobs"].values()
    ).lower()

    assert "pytest" not in collect_runs
    assert "playwright install" not in all_runs
    assert "install chromium" not in all_runs
    assert "--with-deps" not in all_runs
    assert "python -m pytest" not in collect_runs


def test_contract_check_is_tiny_offline_smoke_only():
    workflow, _text = load_workflow()
    job = workflow["jobs"]["contract-check"]
    runs = _job_runs(job)
    assert "tests/test_daily_collection_contract.py" in runs
    assert "tests/test_collection_health.py" in runs
    assert "python -m pytest -q" in runs
    # Must not invoke the whole suite.
    assert "tests/" in runs
    for banned in ("tests/test_wechat", "tests/test_discovery", "tests/eval_"):
        assert banned not in runs


def test_crawler_failure_fails_collect_without_continue_on_error():
    workflow, _text = load_workflow()
    collect = workflow["jobs"]["collect"]
    crawl = _step_by_name(collect, "Crawl local-only")
    health = _step_by_name(collect, "Collection health gate")
    assert collect.get("continue-on-error") not in (True, "true")
    assert crawl.get("continue-on-error") not in (True, "true")
    assert health.get("continue-on-error") not in (True, "true")
    assert "python main.py --local-only --date" in crawl["run"]


def test_summary_and_artifact_always_run_with_name_fallback():
    workflow, text = load_workflow()
    collect = workflow["jobs"]["collect"]
    health = _step_by_name(collect, "Collection health gate")
    upload = _step_by_name(collect, "Upload crawl artifacts")

    assert health.get("if") == "always()"
    assert "check_collection_health.py" in health["run"]
    assert upload.get("if") == "always()"
    assert upload["with"]["if-no-files-found"] == "warn"
    artifact_name = upload["with"]["name"]
    assert artifact_name
    assert "github.run_id" in artifact_name
    assert "daily-collection-" in artifact_name
    assert "artifact_name" in artifact_name
    assert "data/" in text and "logs/" in text


def test_network_steps_have_timeouts_and_pip_cache_with_retry():
    workflow, _text = load_workflow()
    collect = workflow["jobs"]["collect"]
    assert collect.get("timeout-minutes") == 90

    setup = next(
        step for step in collect["steps"] if "setup-python" in str(step.get("uses", ""))
    )
    assert setup["with"]["cache"] == "pip"
    assert setup.get("timeout-minutes")

    install = _step_by_name(collect, "Install collection dependencies")
    assert install.get("timeout-minutes")
    assert "pip install -r requirements.txt" in install["run"]
    assert "attempt" in install["run"]

    crawl = _step_by_name(collect, "Crawl local-only")
    assert crawl.get("timeout-minutes")

    cache = next(step for step in collect["steps"] if "cache@" in str(step.get("uses", "")))
    assert cache.get("timeout-minutes")

    upload = _step_by_name(collect, "Upload crawl artifacts")
    assert upload.get("timeout-minutes")


def test_date_parsing_uses_env_and_never_empty_artifact_name():
    _workflow, text = load_workflow()
    assert "inputs.date || ''" not in text
    assert "github.event.inputs.date" in text
    assert "INPUT_DATE" in text
    assert "github.run_id" in text
    assert "Asia/Shanghai" in text


def test_workflow_keeps_dual_insurance_and_forbids_llm_publish():
    _workflow, text = load_workflow()
    lowered = text.lower()
    assert "generate_daily" not in text
    assert "publish.py" not in text
    assert "export_public_bundle" not in text
    assert "run_daily.py" not in text
    assert "${{ secrets." not in text
    assert "wechat_appid" not in lowered
    assert "wechat_secret" not in lowered
    assert "website_repo_token" not in lowered
    assert "deepseek" not in lowered
    assert "llm_api_key" not in lowered
    assert "supabase" not in lowered
    assert "agnes" not in lowered
    assert "--local-only" in text
    assert "data/state" in text
