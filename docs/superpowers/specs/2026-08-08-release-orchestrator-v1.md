# Release Orchestrator v1

**Date:** 2026-08-08  
**Branch:** `feature/release-orchestrator-v1`  
**Status:** STOP at READY_FOR_PUBLISH (dry-run only)

## State machine

DRAFT → GATE_FAILED | EDITORIAL_REVIEW → EDITORIAL_APPROVED → RENDERED →
CHANNEL_CHECKED → CHANNEL_REVIEW → READY_FOR_PUBLISH →
(PUBLISHING | PARTIALLY_PUBLISHED | PUBLISHED)  # defined, not executed

## Integrity

- Channel reviews store `artifact_hash` + `content_fingerprint`
- Content change → revision bump + REVIEW_STALE
- Artifact change after approve → ARTIFACT_CHANGED_AFTER_REVIEW
- Same content_id + revision → stable release_candidate_id

## CLI

```bash
python release.py status <rc>
python release.py preflight <rc>
python release.py plan <rc>
python release.py dry-run <rc>
```
