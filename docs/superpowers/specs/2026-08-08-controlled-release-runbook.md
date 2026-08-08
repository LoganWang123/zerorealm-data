# Controlled Release Runbook (Human Operators)

This runbook is for **real humans**. System/AI/Cursor accounts are never valid
editorial or channel reviewers.

## Default safety

- `PUBLISH_DISABLED=true` (default). While enabled, `execute()` refuses all real side effects.
- Default CLI mode is `DRY_RUN`.
- Presence of WeChat API keys or GitHub tokens **never** upgrades mode to `PRODUCTION`.

### EMERGENCY STOP

```bash
export PUBLISH_DISABLED=true
```

All controlled publish execute paths must stop immediately.

## Correct content identity

- `content_type` is authoritative.
- Insight publishes to `/insight/<slug>` and `content/insight/<slug>.mdx`.
- Daily publishes to `/daily/<slug>` and `content/daily/<...>.mdx`.
- Never derive Daily from Insight, WeChat publish date, or calendar date alone.
- Allowed: same calendar day with Insight=YES and Daily=NONE.

## Future real release order

1. Research verified (claims / knowledge)
2. Editorial approved by a real reviewer
3. Channel renders (website + wechat artifacts)
4. Human channel review per channel (website, wechat)
5. Status reaches `READY_FOR_PUBLISH`
6. `python release.py preflight <rc>`
7. Review website/wechat release plans (`python release.py plan <rc>`)
8. `python release.py confirmation-token <rc>` → `CONFIRM-XXXXXX`
9. Human confirms token matches current revision + fingerprint
10. Execute **one** release transaction (only after kill switch intentionally disabled)
11. Verify each channel (HTTP / WeChat status)
12. Record immutable receipts
13. Resolve partial failures via `recovery-plan` / `retry --channel ...`

## Commands (v1)

```bash
python release.py status <rc>
python release.py preflight <rc>
python release.py plan <rc>
python release.py dry-run <rc>
python release.py confirmation-token <rc>
python release.py publish <rc> --mode DRY_RUN
python release.py transaction <txn_id>
python release.py receipts <rc>
python release.py lock-status <rc>
python release.py recovery-plan <txn_id>
python release.py retry <txn_id> --channel wechat <rc> --confirm CONFIRM-XXXXXX
```

Production execute (future only):

```bash
# DANGEROUS — do not run until Controlled Publisher production backends are enabled
PUBLISH_DISABLED=false python release.py publish <rc> \
  --mode PRODUCTION \
  --confirm CONFIRM-XXXXXX \
  --freepublish-approved
```

v1 adapters are **fake/local**. Even with kill switch off, network WeChat and
production git push are not wired.

## Partial publish

If Website succeeds and WeChat fails:

- overall: `PARTIALLY_PUBLISHED`
- do **not** republish Website
- `python release.py recovery-plan <txn>`
- `python release.py retry <txn> --channel wechat <rc> --confirm ...`

## Rollback capability

| Channel | rollback_supported | Notes |
|---------|--------------------|-------|
| Website | yes (future revert commit) | Not executed in v1 |
| WeChat  | no | Do not assume API can fully unpublish |

## WeChat two-phase rule

1. `CREATE_DRAFT` (separate)
2. Human confirms in WeChat admin / ops process
3. `FREEPUBLISH` only with explicit `FREEPUBLISH_APPROVED` / `--freepublish-approved`

Draft success must **never** auto freepublish.
