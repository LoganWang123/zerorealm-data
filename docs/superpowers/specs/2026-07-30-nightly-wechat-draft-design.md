# Nightly WeChat Draft Design

## Goal

At 23:00 Asia/Shanghai every day, collect that calendar day's retail signals,
generate the operator-focused daily report and media, then create or update a
WeChat Official Account draft. The operator reviews the draft the next morning
and sends it manually between 08:00 and 09:00.

## Schedule

GitHub Actions schedules use UTC, so the workflow runs at `0 15 * * *`.
The report date is resolved inside the job with `TZ=Asia/Shanghai`; it must not
use the runner's UTC date. GitHub Actions may queue scheduled jobs, so 23:00 is
the requested start time rather than a hard real-time guarantee.

## Pipeline

The existing daily workflow remains the single orchestrator:

1. Resolve the current China Standard Time date.
2. Restore crawler deduplication state, generated media, and publication
   manifest state.
3. Run tests and collect the five approved sources.
4. Generate the quality-gated daily report.
5. If a report was generated, run `publish.py` in its default draft mode.
6. Upload data, report, logs, generated media, and publication manifest as
   diagnostic artifacts.
7. Continue the existing website synchronization.

Draft mode creates a new draft on the first successful run. A repeated run for
the same article restores the publication manifest and updates the existing
draft instead of creating a duplicate. It never calls free publishing or mass
notification APIs.

## Credentials and Failure Handling

The workflow requires `DEEPSEEK_API_KEY`, `AGNES_API_KEY`, `WECHAT_APPID`, and
`WECHAT_SECRET`. `WEBSITE_REPO_TOKEN` remains optional and affects only website
synchronization.

A preflight step fails with a clear GitHub Actions error when a required secret
is absent. The publishing CLI returns a non-zero exit status when rendering or
draft creation fails, so the workflow cannot report success without a usable
draft. Artifacts are uploaded with `if: always()` for diagnosis.

## Runtime and Concurrency

The workflow timeout increases from 30 to 60 minutes to allow crawling, LLM
generation, image generation, and WeChat uploads. Existing concurrency remains
non-cancelling so a delayed run is not interrupted by a manual rerun.

## Testing

- A workflow contract test verifies the UTC cron, China date resolution,
  required-secret preflight, draft command, state caches, and diagnostic
  artifact paths.
- A CLI regression test verifies that a failed publish result produces a
  non-zero command exit status.
- The complete Python test suite and Ruff must pass before push.

