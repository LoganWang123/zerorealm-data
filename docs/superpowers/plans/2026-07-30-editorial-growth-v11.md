# ZeroRealm Editorial Growth V11 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified operator-first WeChat draft tonight and make the nightly pipeline reject speculative, repetitive roundup output.

**Architecture:** Tighten the modular daily prompt contract and its regression tests, then create a hand-reviewed V11 article from the collected source set. Curated local images and the existing WeChat draft publisher remain the delivery path; publishing stops at draft creation.

**Tech Stack:** Python 3.12, pytest, YAML/MDX, WeChat draft API

## Global Constraints

- Exactly one core event and at most two supporting signals.
- Draft only; never send or publish automatically.
- Direct source URLs and source-provided numbers only.
- No generic AI-to-smart-cabinet inference.
- Bright documentary images with no fake UI or text.

---

### Task 1: Lock the V11 editorial contract

**Files:**
- Modify: `config/prompts/daily/role.yaml`
- Modify: `config/prompts/daily/style.yaml`
- Modify: `config/prompts/daily/output_template.yaml`
- Test: `tests/test_daily_report.py`

**Interfaces:**
- Consumes: modular prompt composition in `generators/daily_report.py`
- Produces: a prompt that requires one operating metric, one reversible action, and one stop condition

- [ ] **Step 1: Add failing assertions for title, repetition, and direct-operating-impact rules.**
- [ ] **Step 2: Run `pytest tests/test_daily_report.py -q` and confirm the assertions fail.**
- [ ] **Step 3: Update the modular prompt files with the V11 rules.**
- [ ] **Step 4: Re-run the focused and full test suites.**
- [ ] **Step 5: Commit the prompt and tests.**

### Task 2: Produce and validate tonight's article

**Files:**
- Create: `output_daily/2026-07-30.mdx`
- Create: `assets/generated/2026-07-30/*`
- Create: `storage/media/*`

**Interfaces:**
- Consumes: collected 2026-07-30 source data and the V11 article contract
- Produces: a parseable article and complete local media manifest

- [ ] **Step 1: Write the article from the Eastroc result and direct source URL.**
- [ ] **Step 2: Validate schema, title length, source links, section count, and article length.**
- [ ] **Step 3: Generate and visually inspect the cover and body images.**
- [ ] **Step 4: Build a complete media manifest with verified dimensions and hashes.**
- [ ] **Step 5: Run the publishing dry-run checks.**

### Task 3: Create and inspect the WeChat draft

**Files:**
- Modify: `storage/publish_manifest.json`

**Interfaces:**
- Consumes: validated article and local media manifest
- Produces: one WeChat draft identifier for 2026-07-30

- [ ] **Step 1: Run the WeChat draft publisher.**
- [ ] **Step 2: Confirm the result is a draft and no send/publish API was called.**
- [ ] **Step 3: Inspect title, cover, body images, source attribution, and action card in the WeChat UI.**
- [ ] **Step 4: Commit the final article metadata and pipeline changes without secrets.**
