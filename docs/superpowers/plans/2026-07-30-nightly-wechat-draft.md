# Nightly WeChat Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a reliable local 23:00 automation that collects the current
day's signals, generates an operator-focused report, and creates or updates a
WeChat draft without sending it.

**Architecture:** A Codex local cron automation invokes the existing collection,
generation, and draft CLIs in the saved `ZeroRealmAI` project. The publication
CLI exposes failure through its process exit status so the automation can
distinguish a usable draft from a logged failure.

**Tech Stack:** Python 3.11+, pytest, Ruff, Codex local automations

## Global Constraints

- Resolve the content date in Asia/Shanghai.
- Start daily at 23:00 local time.
- Use only WeChat draft mode; never use `--publish` or `--notify-followers`.
- Reuse `storage/manifest` so a same-day rerun updates the existing draft.
- Never print API keys or WeChat credentials.
- Do not modify, commit, or push code during recurring automation runs.

---

### Task 1: Make Draft Failures Observable to Automation

**Files:**
- Modify: `publish.py`
- Test: `tests/test_wechat_publishing.py`

**Interfaces:**
- Consumes: `list[PublishResult | None]` returned by channel workflows.
- Produces: `publish_results_exit_code(results) -> int` and
  `cmd_publish(args) -> int`.

- [ ] **Step 1: Write the failing result-code tests**

```python
def test_publish_results_exit_code_is_nonzero_for_failed_result():
    failed = PublishResult(status=PublishStatus.FAILED, channel="wechat")
    assert publish_results_exit_code([failed]) == 1


def test_publish_results_exit_code_is_zero_for_created_draft():
    created = PublishResult(status=PublishStatus.SUCCESS, channel="wechat")
    assert publish_results_exit_code([created]) == 0
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
pytest tests/test_wechat_publishing.py -q --basetemp .test-tmp
```

Expected: collection or assertion failure because
`publish_results_exit_code` does not exist.

- [ ] **Step 3: Implement the minimal result aggregation**

```python
def publish_results_exit_code(results):
    if not results:
        return 1
    return int(
        any(
            result is None or result.status == PublishStatus.FAILED
            for result in results
        )
    )
```

Collect each workflow result in `cmd_publish`, return the helper's value, and
make `main` call `sys.exit(exit_code)` only when the value is non-zero.

- [ ] **Step 4: Run focused tests and Ruff**

```powershell
pytest tests/test_wechat_publishing.py -q --basetemp .test-tmp
ruff check publish.py tests/test_wechat_publishing.py
```

Expected: all focused tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit**

```powershell
git add publish.py tests/test_wechat_publishing.py
git commit -m "fix: expose draft failures to automation"
```

### Task 2: Create and Verify the Local Schedule

**Files:**
- Modify: Codex automation configuration through `automation_update`
- Verify: automation id returned by the Codex app

**Interfaces:**
- Consumes: saved project id for `D:\soft\AI\ZeroRealmAI`.
- Produces: an active local cron automation named
  `每晚23点生成公众号草稿`.

- [ ] **Step 1: Confirm no matching automation exists**

Inspect `$CODEX_HOME/automations/*/automation.toml` for the automation name or
the phrases `公众号草稿` and `23:00`.

- [ ] **Step 2: Resolve the saved project**

Call `list_projects` and select the project whose path is
`D:\soft\AI\ZeroRealmAI`.

- [ ] **Step 3: Create the automation**

Create an active local cron automation at 23:00. Its prompt must run these
commands for the Asia/Shanghai date:

```powershell
python main.py --date <date> --source "36kr_rss,linkshop_web,tmtpost_rss,winshang_web,ubox_web"
python generate_daily.py --date <date> --history-dir ..\zerorealm-website\content\daily
python publish.py --channel wechat --date <date>
```

The prompt must explicitly forbid `--publish`, `--notify-followers`, code
changes, commits, pushes, and secret output.

- [ ] **Step 4: View and verify the automation**

Use the returned automation id in view mode. Verify that it is active, local,
targets the `ZeroRealmAI` project, and runs daily at 23:00.

### Task 3: Final Verification and Push

**Files:**
- Verify all files changed by Tasks 1 and 2.

**Interfaces:**
- Consumes: committed CLI behavior and active automation.
- Produces: a pushed feature branch with a clean working tree.

- [ ] **Step 1: Run full verification**

```powershell
pytest -q --basetemp .test-tmp
ruff check .
git diff --check
```

Expected: all tests pass, Ruff reports no errors, and Git reports no whitespace
errors.

- [ ] **Step 2: Commit documentation**

```powershell
git add docs/superpowers/specs/2026-07-30-nightly-wechat-draft-design.md docs/superpowers/plans/2026-07-30-nightly-wechat-draft.md
git commit -m "docs: document nightly wechat draft automation"
```

- [ ] **Step 3: Push the verified branch**

```powershell
git push
```

Expected: the remote `codex/content-growth-media-20260730` branch advances to
the verified commit.

