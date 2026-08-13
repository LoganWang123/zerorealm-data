"""Runtime safety net: Actions must stay collection-only even if YAML regresses.

These tests must stay strict. Workflow-shape tests must not skip them.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import generate_daily
import main as crawler_main
from utils.github_actions_safety import (
    GENERATION_SKIP_REASON,
    SAFE_GITHUB_ENV_OVERRIDES,
    configure_github_actions_safety,
    is_github_actions,
    legacy_pipeline_publish_steps_run,
    write_github_actions_safe_env,
)


def test_is_github_actions_only_true_string(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert is_github_actions() is False
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert is_github_actions() is True
    monkeypatch.setenv("GITHUB_ACTIONS", "TRUE")
    assert is_github_actions() is True
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    assert is_github_actions() is False
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    assert is_github_actions() is False


def test_actions_forces_local_only_and_disables_downstream_steps(monkeypatch, tmp_path):
    github_env = tmp_path / "github-env"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_ENV", str(github_env))
    monkeypatch.setenv("WEBSITE_REPO_TOKEN", "super-secret-token")
    monkeypatch.setenv("WECHAT_SECRET", "super-secret-wechat")
    monkeypatch.setenv("SYNC_PUBLIC_BUNDLE", "true")

    assert crawler_main.configure_github_actions_safety() is True
    text = github_env.read_text(encoding="utf-8")
    assert text.splitlines() == [
        "SYNC_PUBLIC_BUNDLE=false",
        "SYNC_LEGACY_DAILY_MDX=false",
        "WEBSITE_REPO_TOKEN=",
        "WECHAT_APPID=",
        "WECHAT_SECRET=",
        "ZEROREALM_LOCAL_IMAGE_CMD=",
    ]
    assert "super-secret-token" not in text
    assert "super-secret-wechat" not in text


def test_write_github_env_helper_uses_temp_file_without_network(tmp_path):
    target = tmp_path / "nested" / "github.env"
    target.parent.mkdir()
    write_github_actions_safe_env(target)
    written = dict(
        line.split("=", 1) for line in target.read_text(encoding="utf-8").splitlines()
    )
    assert written == dict(SAFE_GITHUB_ENV_OVERRIDES)
    write_github_actions_safe_env(None)


def test_actions_without_github_env_still_reports_true(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_ENV", raising=False)
    assert configure_github_actions_safety() is True


def test_main_forces_local_only_under_github_actions_without_flag(monkeypatch, tmp_path):
    github_env = tmp_path / "github-env"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_ENV", str(github_env))
    captured: dict = {}

    async def fake_crawl_all(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(crawler_main, "crawl_all", fake_crawl_all)
    monkeypatch.setattr(
        crawler_main,
        "load_config",
        lambda: ([], {"logging": {"dir": str(tmp_path / "logs"), "level": "INFO"}}),
    )
    monkeypatch.setattr(crawler_main, "setup_logger", lambda *_a, **_k: None)

    assert crawler_main.main(["--date", "2026-08-13"]) == 0
    assert captured["local_only"] is True
    assert github_env.exists()


def test_actions_local_only_skips_supabase_import(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    touched = {"db": False}

    def boom(*_args, **_kwargs):
        touched["db"] = True
        raise AssertionError("storage.db must not run under GITHUB_ACTIONS")

    import storage.db as db_mod

    monkeypatch.setattr(db_mod, "is_db_available", boom)
    asyncio.run(
        crawler_main.crawl_all(
            sources=[],
            settings={
                "output": {"base_dir": str(tmp_path / "data")},
                "logging": {"dir": str(tmp_path / "logs")},
                "digest": {"priority_sources": []},
            },
            run_id="test_gha_local_only",
            local_only=True,
            output_date="2026-08-13",
        )
    )
    assert touched["db"] is False


def test_actions_generation_guard_runs_before_argument_or_credential_access(
    monkeypatch, capsys
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("LLM_API_KEY", "must-not-be-used")
    monkeypatch.setattr(
        generate_daily,
        "load_dotenv",
        lambda: (_ for _ in ()).throw(AssertionError("load_dotenv must not run")),
    )
    monkeypatch.setattr(
        generate_daily.argparse.ArgumentParser,
        "parse_args",
        lambda _self: (_ for _ in ()).throw(AssertionError("arguments were parsed")),
    )

    assert generate_daily.main() == 2
    captured = capsys.readouterr()
    assert GENERATION_SKIP_REASON in captured.out
    assert "must-not-be-used" not in captured.out
    assert "must-not-be-used" not in captured.err


def test_local_generate_daily_still_requires_llm_key(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(generate_daily, "load_dotenv", lambda: None)
    monkeypatch.setattr("sys.argv", ["generate_daily.py"])
    assert generate_daily.main() == 1


def test_local_main_does_not_force_local_only(monkeypatch, tmp_path):
    github_env = tmp_path / "github-env"
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("GITHUB_ENV", str(github_env))
    captured: dict = {}

    async def fake_crawl_all(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(crawler_main, "crawl_all", fake_crawl_all)
    monkeypatch.setattr(
        crawler_main,
        "load_config",
        lambda: ([], {"logging": {"dir": str(tmp_path / "logs"), "level": "INFO"}}),
    )
    monkeypatch.setattr(crawler_main, "setup_logger", lambda *_a, **_k: None)

    assert crawler_main.main(["--date", "2026-08-13"]) == 0
    assert captured["local_only"] is False
    assert not github_env.exists()


def test_non_actions_safety_hook_is_a_noop(monkeypatch, tmp_path):
    github_env = tmp_path / "github-env"
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("GITHUB_ENV", str(github_env))

    assert crawler_main.configure_github_actions_safety() is False
    assert not Path(github_env).exists()


def test_legacy_pipeline_ifs_skip_publish_under_safe_env():
    """Old Daily Pipeline step `if:` predicates after GITHUB_ENV override.

    Checkout website is evaluated BEFORE main.py, so a job-level token still
    checks out; that is not a publish. Export Public Bundle has no `if` and
    still runs locally without git push. Images / website push / production
    verify all skip when token is emptied and generated=false.
    """
    env = dict(SAFE_GITHUB_ENV_OVERRIDES)
    steps = legacy_pipeline_publish_steps_run(
        website_repo_token=env["WEBSITE_REPO_TOKEN"],
        sync_public_bundle=env["SYNC_PUBLIC_BUNDLE"],
        generated="false",
    )
    assert steps["generate_images"] is False
    assert steps["publish_website"] is False
    assert steps["verify_production"] is False
    assert steps["website_token_warning"] is True
    assert steps["export_public_bundle"] is True
    assert steps["checkout_website"] is False


def test_generate_daily_cli_exits_2_on_actions_without_llm(monkeypatch):
    env = os.environ.copy()
    env["GITHUB_ACTIONS"] = "true"
    env["LLM_API_KEY"] = "must-not-be-used"
    env.pop("GITHUB_ENV", None)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "generate_daily.py")],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert GENERATION_SKIP_REASON in result.stdout
    assert "must-not-be-used" not in result.stdout
    assert "must-not-be-used" not in result.stderr


def test_workflow_shape_detector_covers_both_forms():
    from workflow_shapes import is_new_collection_workflow

    assert is_new_collection_workflow(
        {"jobs": {"collect": {}, "contract-check": {}}}, ""
    ) is True
    assert is_new_collection_workflow(
        {"jobs": {"pipeline": {}}}, "generate_daily.py"
    ) is False
