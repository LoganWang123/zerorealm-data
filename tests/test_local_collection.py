"""Local daily collection: script, launchd assets, main --local-only, status contract."""

from __future__ import annotations

import asyncio
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import main as main_mod


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_local_collection.sh"
INSTALL = ROOT / "scripts" / "macos" / "install_local_collection_launchd.sh"
UNINSTALL = ROOT / "scripts" / "macos" / "uninstall_local_collection_launchd.sh"
PLIST_TEMPLATE = (
    ROOT / "scripts" / "macos" / "com.zerorealm.local-collection.plist.template"
)


def _non_comment_lines(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")
    )


def test_run_local_collection_script_is_executable_and_safe():
    text = SCRIPT.read_text(encoding="utf-8")
    body = _non_comment_lines(text)
    mode = SCRIPT.stat().st_mode

    assert mode & stat.S_IXUSR
    assert "set -euo pipefail" in text
    assert "Asia/Shanghai" in text
    assert ".venv/bin/python" in text
    assert '"${PYTHON}" "${ROOT}/main.py" --local-only --date "${DATE}"' in text
    assert "latest_status.json" in text
    assert "latest_handoff.md" in text
    assert "run.lock" in text

    for key in (
        "LLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "AGNES_API_KEY",
        "ANYSEARCH_API_KEY",
        "WECHAT_APPID",
        "WECHAT_SECRET",
        "WEBSITE_REPO_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_KEY",
    ):
        assert f"unset" in text and key in text

    assert not re.search(r'(?<!/)generate_daily\.py', body.split("forbidden_in_this_job")[0])
    assert not re.search(r'(?<!["/])publish\.py\b', body.split("forbidden_in_this_job")[0])
    assert "git push" not in body.split("forbidden_in_this_job")[0]
    assert "cursor-agent" not in body.split("forbidden_in_this_job")[0]
    assert re.search(r'\bagy\b', body.split("forbidden_in_this_job")[0]) is None


def test_run_local_collection_only_invokes_main_local_only():
    text = SCRIPT.read_text(encoding="utf-8")
    body = _non_comment_lines(text)
    invoke_lines = [
        line.strip()
        for line in text.splitlines()
        if "${PYTHON}" in line and "main.py" in line and not line.strip().startswith("#")
    ]
    assert invoke_lines == [
        '"${PYTHON}" "${ROOT}/main.py" --local-only --date "${DATE}" 2>&1 | tee -a "${RUN_LOG}"'
    ]
    assert not re.search(r'(^|[\s;|&])\S*python\S*\s+generate_daily', body, re.M)
    assert not re.search(r'(^|[\s;|&])\S*python\S*\s+publish\.py', body, re.M)
    assert not re.search(r'(^|[\s;|&])git\s+push\b', body, re.M)
    assert not re.search(r'(^|[\s;|&])cursor-agent\b', body, re.M)
    assert not re.search(r'(^|[\s;|&])agy\b', body, re.M)



def test_launchd_template_and_install_use_dynamic_absolute_paths():
    template = PLIST_TEMPLATE.read_text(encoding="utf-8")
    install = INSTALL.read_text(encoding="utf-8")
    uninstall = UNINSTALL.read_text(encoding="utf-8")

    assert "<integer>23</integer>" in template
    assert "<integer>0</integer>" in template
    assert "__REPO_ROOT__" in template
    assert "__LABEL__" in template
    assert "StartCalendarInterval" in template
    assert "Asia/Shanghai" in template
    assert "<key>RunAtLoad</key>" in template
    assert "<true/>" in template
    assert "/Users/" not in template

    assert "set -euo pipefail" in install
    assert "__REPO_ROOT__" in install
    assert "sed" in install
    assert "LaunchAgents" in install
    assert "bootout" in install or "unload" in install
    assert "daily 23:00" in install

    assert "LaunchAgents" in uninstall
    assert "bootout" in uninstall or "unload" in uninstall
    assert INSTALL.stat().st_mode & stat.S_IXUSR
    assert UNINSTALL.stat().st_mode & stat.S_IXUSR


def test_main_parser_accepts_local_only_and_keeps_legacy_flags():
    parser = main_mod.build_parser()
    args = parser.parse_args(["--local-only", "--date", "2026-08-13", "--source", "x"])
    assert args.local_only is True
    assert args.date == "2026-08-13"
    assert args.source == "x"

    legacy = parser.parse_args(["--debug"])
    assert legacy.local_only is False
    assert legacy.debug is True


def test_local_only_does_not_touch_storage_db(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")

    touched = {"db": False}

    def boom(*_args, **_kwargs):
        touched["db"] = True
        raise AssertionError("storage.db must not run in local-only mode")

    import storage.db as db_mod

    monkeypatch.setattr(db_mod, "is_db_available", boom)
    monkeypatch.setattr(db_mod, "get_client", boom)

    log_dir = tmp_path / "logs"
    data_dir = tmp_path / "data"
    settings = {
        "output": {"base_dir": str(data_dir)},
        "logging": {"dir": str(log_dir)},
        "digest": {"priority_sources": []},
        "quality": {},
        "dedup": {},
    }

    asyncio.run(
        main_mod.crawl_all(
            sources=[],
            settings=settings,
            run_id="test_local_only",
            local_only=True,
            output_date="2026-08-13",
        )
    )

    assert touched["db"] is False
    assert (log_dir / "test_local_only_metrics.json").exists()


def test_non_local_mode_may_consult_storage_db(monkeypatch, tmp_path):
    called = {"available": False}

    def fake_available():
        called["available"] = True
        return False

    import storage.db as db_mod

    monkeypatch.setattr(db_mod, "is_db_available", fake_available)

    settings = {
        "output": {"base_dir": str(tmp_path / "data")},
        "logging": {"dir": str(tmp_path / "logs")},
        "digest": {"priority_sources": []},
    }
    asyncio.run(
        main_mod.crawl_all(
            sources=[],
            settings=settings,
            run_id="test_remote_ok",
            local_only=False,
            output_date="2026-08-13",
        )
    )
    assert called["available"] is True


def test_status_handoff_contract_shape_from_script_helpers(tmp_path):
    """Smoke-run script against a fake python that exits 0; assert contract files."""
    mini = tmp_path / "repo"
    (mini / "scripts").mkdir(parents=True)
    (mini / "logs").mkdir()
    script_copy = mini / "scripts" / "run_local_collection.sh"
    script_copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    script_copy.chmod(script_copy.stat().st_mode | stat.S_IXUSR)
    (mini / "main.py").write_text("# placeholder\n", encoding="utf-8")

    venv_bin = mini / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    venv_python = venv_bin / "python"
    venv_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${1:-}\" == \"-c\" ]]; then\n"
        "  shift\n"
        "  code=\"$1\"\n"
        "  shift\n"
        "  exec /usr/bin/env python3 -c \"$code\" \"$@\"\n"
        "fi\n"
        "echo fake-main \"$@\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    venv_python.chmod(venv_python.stat().st_mode | stat.S_IXUSR)

    home = tmp_path / "home_should_stay_empty"
    home.mkdir()
    env = os.environ.copy()
    env["LOCAL_COLLECTION_DATE"] = "2026-08-13"
    env["HOME"] = str(home)

    result = subprocess.run(
        ["bash", str(script_copy)],
        cwd=str(mini),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout

    status_path = mini / "logs" / "local_collection" / "latest_status.json"
    handoff_path = mini / "logs" / "local_collection" / "latest_handoff.md"
    assert status_path.exists()
    assert handoff_path.exists()

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["schema_version"] == 1
    assert status["mode"] == "local-only"
    assert status["status"] == "ok"
    assert status["date"] == "2026-08-13"
    assert status["exit_code"] == 0
    assert status["command"] == ["main.py", "--local-only", "--date", "2026-08-13"]
    assert status["digest_hint"] == "data/digest/2026/08/13"
    assert "generate_daily.py" in status["forbidden_in_this_job"]
    assert status["next_llm_work"]["cursor_model"] == "auto"
    assert status["next_llm_work"]["antigravity_model"] == "gemini-3.6-flash-medium"

    handoff = handoff_path.read_text(encoding="utf-8")
    assert "local-only" in handoff
    assert "ai-delivery.sh" in handoff
    assert "Antigravity" in handoff

    # Collection script must not install launchd or write ops artifacts into HOME.
    assert not (home / "Library" / "LaunchAgents").exists()
    assert not (home / "logs").exists()
    assert not any(home.rglob("*.plist"))


def test_install_script_render_does_not_require_home_when_dry_checked():
    template = PLIST_TEMPLATE.read_text(encoding="utf-8")
    assert "/Users/" not in template
    assert "${HOME}" not in template
    assert "__REPO_ROOT__" in INSTALL.read_text(encoding="utf-8")
