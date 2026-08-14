# Changelog

## 2026-08-15 — Ops retrospective + freshness-gated import

- Recorded Daily Collection scheduled run 31817014485 (success) as technical metrics only
- Added local WeChat/Zhihu report discovery, freshness gate, and operating retrospective
- Stale channel reports never fill `current_experiment` counts

## Unreleased — Research Platform Phase 8–11 (local RC)

### Phase 8
- Disabled Agnes image generation on production paths
- Added LocalImageGenerator, ImageBrief, prompt packages, programmatic templates
- CI no longer injects AGNES_* for media

### Phase 9
- Company audit CLI, content lint, readiness, review queue
- Source audit with explicit `network_not_checked`

### Phase 10
- Industry map migration dry-run tool + dataset export
- Relation index helper

### Phase 11
- Content package exporter (no Agnes media)
- Release package under `release/zerorealm-research-platform-v1/`
- Media generation policy docs
