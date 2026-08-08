# AnySearch Source Discovery v1 Design

**Date:** 2026-08-08  
**Branch:** `feature/anysearch-discovery-provider`  
**Status:** Implemented (adapter + mock tests; live smoke pending API key in env)

## Goal

Add an independent Discovery layer:

```text
AnySearch → SearchCandidate → Candidate Pool
  → HTML/Playwright Fetch → RawItem
  → research (SourceDocument / Evidence / Claim)
  → validators → Candidate VERIFIED / REJECTED
```

Stops before Daily / Insight / Publish. Does not change `main.py` or `daily-crawl`.

## Module layout

```text
discovery/
  models.py
  providers/base.py
  providers/anysearch.py
  pool.py
  dedupe.py
  scoring.py
  fetch.py
  pipeline.py
  cli.py
discover.py                 # thin CLI entry
config/source_queries.yaml  # query registry scaffold
```

## Hard rules

1. `snippet` / `provider_content` are discovery-only — never `SourceDocument` / Evidence body.
2. Only successfully fetched original URL content may enter `RawItem` → research.
3. Candidate `VERIFIED` ≠ `ClaimStatus.VERIFIED` (claims stay `draft`).
4. Publishing gate adds non-bypassable `SEARCH_SNIPPET_AS_EVIDENCE`.
5. `ANYSEARCH_API_KEY` from env only — never logged or committed.

## CLI

```bash
python discover.py --query "智能柜" --dry-run
python discover.py --query "智能柜" --stage verify --limit 5
python -m discovery.cli --query "智能柜" --persist
```

## Lineage

```text
candidate_id → raw_item_id → source_document_id → evidence_ids[] / claim_ids[]
```

## Tests

- `tests/test_discovery_pipeline.py` (mock provider / no live AnySearch)
- Editorial gate coverage for `SEARCH_SNIPPET_AS_EVIDENCE`

## Leftovers

- Live smoke with real `ANYSEARCH_API_KEY`
- Wire `config/source_queries.yaml` into CLI (`--topic` / `--company`)
- Optional Playwright auto-fallback when HTML extract is empty
- Persist discovery metadata onto durable research store (beyond candidate pool JSON)
