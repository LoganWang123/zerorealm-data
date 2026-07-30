# Operator Content Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Focus ZeroRealm content on smart-cabinet operators, add an explicit follower-notification path, replace generic media, and align the website with the operator workflow.

**Architecture:** The data repository owns editorial policy, report validation, WeChat delivery, and generation prompts. The website repository consumes a versioned media manifest, renders an accessible three-stage story, and stores the approved poster and film. External delivery and generation stay behind explicit commands; tests use local fakes.

**Tech Stack:** Python 3.14, pytest, requests, YAML, Next.js 16, React 19, TypeScript, Node test runner, Agnes media API, built-in image generation, FFmpeg/ffprobe.

## Global Constraints

- Primary audience: smart-cabinet owners and operating managers.
- Article length target: 1,000–1,500 Chinese characters.
- One core story and at most two supporting signals.
- Every included signal requires a direct HTTP(S) source URL.
- Free publication must never be described as follower notification.
- Real mass notification requires an explicit CLI flag and is never invoked by tests.
- Generated media contains no readable text, logos, watermarks, fake dashboards, neon AI beams, or generic AI characters.
- Preserve unrelated untracked files in the original repositories.

---

### Task 1: Operator editorial policy and generated-report gate

**Files:**
- Modify: `config/prompts/daily/role.yaml`
- Modify: `config/prompts/daily/style.yaml`
- Modify: `config/prompts/daily/insight.yaml`
- Modify: `config/prompts/daily/seo.yaml`
- Modify: `config/prompts/daily/output_template.yaml`
- Modify: `generators/daily_report.py`
- Modify: `tests/test_daily_report.py`

**Interfaces:**
- Produces `validate_generated_report(parsed: dict) -> None`.
- Extends `find_duplicate_headline(parsed, history_dir)` to reject materially similar recent titles.

- [ ] Write failing tests for a near-duplicate headline, missing direct source URL, more than one core story, more than two supporting signals, and a core story without an operating metric.
- [ ] Run focused tests and confirm each fails for the missing behavior.
- [ ] Implement the minimal validation and recent-title similarity boundary.
- [ ] Replace the nine-module multi-persona prompt with the approved operator format.
- [ ] Run focused and full daily-report tests.
- [ ] Commit the editorial policy and gate.

### Task 2: Explicit follower notification and follower comments

**Files:**
- Modify: `publishing/base.py`
- Modify: `publishing/models.py`
- Modify: `publishing/steps.py`
- Modify: `publishing/wechat/client.py`
- Modify: `publishing/wechat/publisher.py`
- Modify: `publish.py`
- Modify: `tests/test_wechat_publishing.py`

**Interfaces:**
- Produces `WechatClient.send_mass_article(media_id: str) -> str`.
- Extends publisher calls with `notify_followers: bool = False`.
- Adds CLI mode `--notify-followers`, mutually exclusive with free `--publish`.

- [ ] Write failing tests for the all-follower `mpnews` payload, explicit notification routing, non-notifying free publication, mutually exclusive CLI flags, and enabled follower comments.
- [ ] Run focused tests and verify RED.
- [ ] Implement the minimal API, publisher, pipeline, and CLI changes.
- [ ] Update CLI help so `--publish` says it does not notify followers.
- [ ] Run WeChat and full Python tests.
- [ ] Commit the notification boundary.

### Task 3: Credible operator-focused media prompts

**Files:**
- Modify: `publishing/media_generation/prompts.py`
- Modify: `tests/test_media_generation.py`

**Interfaces:**
- Produces daily prompt version `daily-v2`.
- Produces homepage prompt version `homepage-v3` with exactly three operator-workflow scenes.

- [ ] Write failing tests that reject generic AI visual language and require cabinet inspection, evidence review, and operating action.
- [ ] Run focused tests and verify RED.
- [ ] Implement the daily and homepage prompt contracts.
- [ ] Run media-generation and assembly tests.
- [ ] Commit the new prompt versions.

### Task 4: Homepage story contract and operator messaging

**Files in `zerorealm-website`:**
- Modify: `lib/home-media.ts`
- Modify: `components/home/HomeMedia.tsx`
- Modify: `components/home/Hero.tsx`
- Modify: `public/media/home/homepage-media.json`
- Modify: `tests/home-media.test.ts`

**Interfaces:**
- Adds `story: Array<{ label: string; description: string }>` to `HomeMediaManifest`.
- The parser requires exactly three non-empty story beats.

- [ ] Write a failing parser test for missing or malformed story beats.
- [ ] Run the Node test and verify RED.
- [ ] Implement manifest parsing and render the three explanatory beats outside the video.
- [ ] Update hero and media copy for the approved operator promise.
- [ ] Run tests, lint, type-check, and build.
- [ ] Commit the website contract and copy.

### Task 5: Generate and integrate replacement assets

**Files:**
- Create or replace in data repository: `assets/covers/cover-2026-07-30.png`
- Replace in website repository: `public/media/home/hero.png`
- Replace in website repository: `public/media/home/showcase.mp4`
- Modify in website repository: `public/media/home/homepage-media.json`

**Interfaces:**
- Daily cover is a text-free documentary retail image suitable for a WeChat crop.
- Homepage media is 1920×1080, 14–16 seconds, and matches the three story beats.

- [ ] Generate the daily cover and homepage poster with the built-in image tool.
- [ ] Inspect both images and iterate once if the focal subject, crop safety, or realism fails.
- [ ] Generate three homepage scenes with the approved homepage-v3 prompts and assemble them.
- [ ] Inspect frames near 1, 6, and 11 seconds; reject fake text, generic AI imagery, broken anatomy, or repeated scenes.
- [ ] Update hashes and metadata in the manifest.
- [ ] Run full repository verification.
- [ ] Commit approved assets and manifest.

### Task 6: Documentation, final verification, and push

**Files:**
- Modify: `README.md`
- Modify: `public/media/home/README.md` in the website repository.

- [ ] Document the distinction between free publication and follower notification.
- [ ] Document the operator editorial gate and media-v3 contract.
- [ ] Run all Python tests and code-quality checks.
- [ ] Run all website tests, lint, TypeScript checking, and production build.
- [ ] Check both diffs for secrets, temporary files, and unrelated changes.
- [ ] Push both `codex/content-growth-media-20260730` branches to origin.

