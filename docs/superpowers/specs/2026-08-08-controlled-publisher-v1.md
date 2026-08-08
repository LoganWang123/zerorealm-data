"""Controlled Publisher v1 design notes."""

## Scope

Safe channel execution after `READY_FOR_PUBLISH`:

- Website adapter (create-only, fake git backend)
- WeChat adapter (CREATE_DRAFT vs FREEPUBLISH separated, fake backend)
- PublishTransaction + receipts + release lock
- Confirmation tokens bound to revision/fingerprint
- Post-publish mock verification
- Partial publish recovery model

## Defaults

- `PUBLISH_DISABLED=true`
- execution mode `DRY_RUN`
- no real WeChat API, no production git push

## Package

`content/controlled_publish/` — separate from legacy `publishing.factory.PublisherFactory`.
