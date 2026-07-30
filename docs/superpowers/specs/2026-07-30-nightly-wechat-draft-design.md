# Nightly WeChat Draft Design

## Goal

At 23:00 Asia/Shanghai every day, collect that calendar day's retail signals,
generate the operator-focused daily report and media, then create or update a
WeChat Official Account draft. The operator reviews the draft the next morning
and sends it manually between 08:00 and 09:00.

## Schedule and Execution Environment

A Codex local cron automation runs daily at 23:00 in the saved `ZeroRealmAI`
project. It resolves the report date in Asia/Shanghai and operates in the local
`zerorealm-data` checkout, where the existing `.env` and persistent publication
manifest are available.

The existing GitHub Actions workflow remains unchanged because standard
GitHub-hosted runners have dynamic outbound IP addresses. That makes them a
poor fit for WeChat API access when an IP allowlist is enabled. The local task
also avoids putting WeChat credentials into an additional remote environment.

## Pipeline

The automation performs one bounded local sequence:

1. Resolve the current China Standard Time date.
2. Collect the five approved sources for that date.
3. Generate the quality-gated daily report using website history for issue
   numbering and duplicate checks.
4. Run `publish.py` in its default draft mode.
5. Verify the report file, command result, and draft identifier.

Draft mode creates a new draft on the first successful run. A repeated run for
the same article uses the persistent local publication manifest and updates the
existing draft instead of creating a duplicate. It never calls free publishing
or mass notification APIs. The automation does not modify code, commit, or
push Git changes.

## Credentials and Failure Handling

The local `.env` must provide `LLM_API_KEY`, `AGNES_API_KEY`, `WECHAT_APPID`,
and `WECHAT_SECRET`. Secret values must never be printed in automation output.

A preflight check fails with a clear error when a required value is absent.
The publishing CLI returns a non-zero exit status when rendering or draft
creation fails, so the automation cannot report success without a usable
draft. The run reports the failing stage and an actionable reason.

## Delivery Window

The requested start time is 23:00. Crawling, text generation, image generation,
and WeChat uploads normally place the draft in the account before 00:10. The
operator reviews it after 07:30 and manually sends it between 08:00 and 09:00.

## Testing

- A CLI regression test verifies that a failed publish result produces a
  non-zero command exit status.
- The complete Python test suite and Ruff must pass before push.
- The created automation is viewed after creation to verify its active status,
  project target, local execution environment, and daily 23:00 schedule.
