# Scheduled Visual Draft Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and validate issue visuals, verify the deployed website, and create a readback-verified WeChat draft on a Monday/Wednesday/Friday schedule.

**Architecture:** Reuse the existing dry-run publishing pipeline as the media preparation boundary, then sync its deterministic asset bundle to the website. Only after production verification runs successfully does the existing draft publisher upload images and call the WeChat draft API.

**Tech Stack:** GitHub Actions, Python 3.11, pytest, PyYAML, requests, Agnes image API, WeChat Official Account API.

## Global Constraints

- Never call free-publish or mass-send from the scheduled workflow.
- Require one 900x383 PNG cover and three 1280x720 PNG body images.
- Stop on media, deployment, upload, or API readback failure.
- Run at 06:00 Asia/Shanghai on Monday, Wednesday, and Friday.

---

### Task 1: Lock down scheduled workflow behavior

**Files:**
- Create: `tests/test_scheduled_release_workflow.py`
- Modify: `.github/workflows/daily-crawl.yaml`

**Interfaces:**
- Consumes: generated `output_daily/YYYY-MM-DD.mdx`
- Produces: deployed report/images and a draft-only command

- [x] Write failing tests for cron, media-to-website-to-draft ordering, and forbidden delivery flags.
- [x] Run the focused test and confirm all three assertions fail against the old workflow.
- [x] Add media preparation, website image sync, production polling, draft creation, caching, and secrets.
- [x] Run the focused workflow tests and confirm they pass.

### Task 2: Verify every WeChat draft through the API

**Files:**
- Modify: `publishing/wechat/publisher.py`
- Modify: `tests/test_wechat_publishing.py`
- Modify: `tests/test_wechat_media.py`

**Interfaces:**
- Consumes: `WechatClient.get_draft(media_id)` and the expected article payload
- Produces: a successful result only when stored title, cover, image URLs, contacts, and source URL match

- [x] Write a failing regression test for truncated API readback.
- [x] Confirm the old publisher incorrectly reports success.
- [x] Add fail-closed readback validation before any optional delivery call.
- [x] Update image-pipeline fakes to return the stored draft.
- [x] Run the complete relevant test set and confirm zero failures.

### Task 3: Final repository verification

**Files:**
- Verify: all changed workflow, publisher, test, specification, and plan files

**Interfaces:**
- Consumes: the completed changes
- Produces: reviewable commit and push

- [x] Run the full pytest suite with a writable repository-local base temp directory.
- [x] Run Ruff against changed Python files.
- [x] Parse the workflow with PyYAML and inspect `git diff --check`.
- [ ] Commit only the scoped files, preserving unrelated local changes.
- [ ] Push the data repository branch and report any GitHub secret still requiring manual configuration.
