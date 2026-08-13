"""Cloud daily-collection workflow: cron kept; no LLM / publish / secrets.

TODO: Once the GitHub PAT has `workflow` scope, push the slim Daily Collection
YAML and delete the legacy dual-shape branches. Runtime GHA guards stay until
the remote YAML no longer generates or publishes.
"""

from pathlib import Path

import pytest

from workflow_shapes import is_new_collection_workflow, load_daily_workflow


def load_workflow():
    workflow, _text = load_daily_workflow()
    return workflow


def _require_new_workflow():
    workflow, text = load_daily_workflow()
    if not is_new_collection_workflow(workflow, text):
        pytest.skip(
            "legacy Daily Pipeline still on remote; strict new-workflow "
            "contract applies after workflow-scope PAT can push YAML"
        )
    return workflow, text


def test_workflow_has_schedule_cron_015_and_dispatch():
    workflow = load_workflow()
    on = workflow[True]
    assert "schedule" in on
    assert "workflow_dispatch" in on
    assert any(item.get("cron") == "0 15 * * *" for item in on["schedule"])


def test_runtime_gha_guards_exist_independent_of_workflow_shape():
    main_src = Path("main.py").read_text(encoding="utf-8")
    gen_src = Path("generate_daily.py").read_text(encoding="utf-8")
    assert "configure_github_actions_safety" in main_src
    assert "GITHUB_ACTIONS" in main_src
    assert "is_github_actions" in gen_src
    assert "return 2" in gen_src


def test_legacy_workflow_keeps_cron_and_invokes_guarded_scripts():
    workflow, text = load_daily_workflow()
    if is_new_collection_workflow(workflow, text):
        pytest.skip("slim Daily Collection workflow present")
    assert "python main.py" in text
    assert "generate_daily.py" in text
    assert any(item.get("cron") == "0 15 * * *" for item in workflow[True]["schedule"])


def test_workflow_runs_local_only_crawl_and_artifacts():
    workflow, text = _require_new_workflow()
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
    _workflow, text = _require_new_workflow()
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
