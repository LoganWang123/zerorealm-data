"""Dual-insurance cloud schedule: cron retained, no LLM / publish.

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


def test_workflow_keeps_beijing_2300_cron_and_manual_dispatch():
    workflow = load_workflow()
    on = workflow[True]
    assert "workflow_dispatch" in on
    assert "schedule" in on
    crons = [item["cron"] for item in on["schedule"]]
    assert "0 15 * * *" in crons


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
    on = workflow[True]
    assert "0 15 * * *" in [item["cron"] for item in on["schedule"]]
    assert "python main.py" in text
    assert "generate_daily.py" in text


def test_workflow_is_local_only_collection_without_llm_publish():
    workflow, text = _require_new_workflow()
    lowered = text.lower()
    jobs = workflow["jobs"]
    assert "collect" in jobs
    assert "contract-check" in jobs
    assert jobs["collect"].get("needs") in (None, [], "")

    steps = jobs["collect"]["steps"]
    names = [step.get("name", "") for step in steps]
    runs = "\n".join(step.get("run", "") for step in steps if isinstance(step.get("run"), str))

    assert "Install collection dependencies" in names
    assert "Crawl local-only (no LLM / no remote store)" in names
    assert "Collection health gate and summary" in names
    assert "Upload crawl artifacts" in names
    assert "Restore cross-run dedup state" in names
    assert "pytest" not in runs
    assert "playwright install" not in text.lower()
    assert "install chromium" not in text.lower()
    assert "--with-deps" not in text.lower()

    assert "python main.py --local-only --date" in runs
    assert "data/state" in text
    assert "upload-artifact@" in text
    assert "cache@" in text

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


def test_local_launchd_is_boot_supplement_with_2300_path():
    template = Path(
        "scripts/macos/com.zerorealm.local-collection.plist.template"
    ).read_text(encoding="utf-8")

    assert "<key>Hour</key>" in template
    assert "<integer>23</integer>" in template
    assert "<key>Minute</key>" in template
    assert "<integer>0</integer>" in template
    assert "<key>RunAtLoad</key>" in template
    assert "<true/>" in template
    assert "run_local_collection.sh" in template
    assert "__REPO_ROOT__" in template
    assert "/Users/" not in template
