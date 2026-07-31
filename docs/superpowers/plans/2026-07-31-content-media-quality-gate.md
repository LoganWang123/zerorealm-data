# Content and Media Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block unreviewed or visually unsuitable daily images and replace the current WeChat draft media.

**Architecture:** Extend `MediaAsset` with explicit visual-review metadata. `MediaValidator` enforces those fields after hash and dimension checks, while generated assets default to unreviewed. Manually reviewed assets record the approval in the date manifest.

**Tech Stack:** Python, pytest, Pillow, WeChat draft API.

## Global Constraints

- Never publish or notify followers.
- No AI-generated text inside images.
- Every approved image must depict a smart-cabinet operation and have a matching SHA-256.

### Task 1: Add visual-review validation

**Files:**
- Modify: `publishing/models.py`
- Modify: `publishing/media_generation/validation.py`
- Test: `tests/test_media_generation.py`

- [ ] Write failing tests for missing review metadata.
- [ ] Run the focused tests and confirm the expected failure.
- [ ] Add review fields and validator checks.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Replace daily media

**Files:**
- Modify: `assets/covers/cover-2026-07-30.png`
- Runtime: `assets/generated/2026-07-30/*`

- [ ] Copy the three visually reviewed smart-cabinet photographs.
- [ ] Render the cover text deterministically with Pillow.
- [ ] Record reviewed hashes and review fields in the manifest.
- [ ] Run a dry-run publication and confirm media validation passes.

### Task 3: Update the WeChat draft

- [ ] Update the existing draft without `--publish` or `--notify-followers`.
- [ ] Read the draft back through the API.
- [ ] Confirm title, image count, and image hashes.

