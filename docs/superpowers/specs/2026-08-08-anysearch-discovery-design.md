# AnySearch Source Discovery v1 Design

**Date:** 2026-08-08  
**Branch:** `feature/anysearch-discovery-provider`  
**Status:** Complete for Discovery → Verify (no Daily/Publish)

## Goal

```text
Query / Topic / Company
→ AnySearch
→ SearchCandidate
→ Durable Candidate Pool
→ Dedupe / Score
→ HTML → Playwright fallback
→ RawItem
→ SourceDocument / Evidence / Claim
→ research validators
→ VERIFIED / REJECTED
```

Stops before Daily / Insight / Publish. Does not change `main.py` or `daily-crawl`.

## Dual intake

```text
Registry (sources.yaml) ──┐
                          ├→ RawItem → research/
Discovery (AnySearch) ────┘
```

## Module layout

```text
discovery/
  models.py
  queries.py              # config/source_queries.yaml
  providers/base.py
  providers/anysearch.py
  pool.py                 # durable data/state/candidate_pool.json
  dedupe.py
  scoring.py
  fetch.py                # HTML → Playwright fallback
  pipeline.py
  cli.py
discover.py
config/source_queries.yaml
```

## CLI

```bash
python discover.py --query "智能柜" --dry-run
python discover.py --topic smart-cabinet --dry-run
python discover.py --company "友宝" --dry-run
python discover.py --query "智能柜" --stage verify --limit 3
```

## Hard rules

1. `snippet` / `provider_content` are discovery-only.
2. Candidate `VERIFIED` ≠ `ClaimStatus.VERIFIED` (claims stay draft).
3. Publishing gate: non-bypassable `SEARCH_SNIPPET_AS_EVIDENCE`.
4. `ANYSEARCH_API_KEY` from env / `.env` only.

## Durable pool

Path: `data/state/candidate_pool.json` (gitignored under `data/`, durable across runs, not `.cache`).

## Leftovers (out of v1)

- Auto topic/company scheduling in CI
- Richer source-tier scoring
- Wire verified candidates into research review queue UI (manual)
