# AnySearch Source Discovery Design (v1 + v1.1)

**Date:** 2026-08-08  
**Branches:**  
- v1: `feature/anysearch-discovery-provider` (merged)  
- v1.1: `feature/discovery-quality-review-v1`  
**Status:** Discovery → Verify → Research Review Queue (no Daily/Publish)

## Goal architecture

```text
                Source Intake
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
Registry Sources              AnySearch
sources.yaml                  Discovery
        │                         │
        │                  SearchCandidate
        │                         │
        │                  Candidate Pool
        │                         │
        │                  Dedupe / Score
        │                         │
        │              HTML → Playwright
        │                         │
        └─────────────┬───────────┘
                      ▼
                   RawItem
                      │
                      ▼
            SourceDocument
            Evidence
            Claim(draft)
                      │
                      ▼
             research validators
                      │
                Candidate
            VERIFIED / REJECTED
                      │
                VERIFIED only
                      ▼
              Source Quality
              + Freshness
              + Discovery Score
                      │
                      ▼
            Research Review Queue
                      │
                      ▼
              Human Research Review
```

Stops before Daily / Insight / Publish. Does not change `main.py` or `daily-crawl`.

## Four distinct concepts

| Concept | Meaning |
|---|---|
| **Candidate VERIFIED** | Original URL fetched, body valid, lineage complete, research validators passed — research-eligible evidence material |
| **Evidence validity** | Structural / lineage / content checks in `research/validators` |
| **Discovery Score** | Whether a candidate is worth prioritizing for human research (relevance + tier + freshness + matches) |
| **Research Review Queue** | Human triage (`PENDING` / `APPROVED` / `REJECTED` / `DEFERRED`) after Candidate VERIFIED |
| **ClaimStatus.VERIFIED** | Human fact verification in the research workflow — **never** auto-set by Discovery or Review Queue approve |

## Dual intake

```text
Registry (sources.yaml) ──┐
                          ├→ RawItem → research/
Discovery (AnySearch) ────┘
```

`sources.yaml` is not migrated away when Source Tier exists.

## Module layout

```text
discovery/
  models.py
  queries.py              # config/source_queries.yaml
  providers/base.py
  providers/anysearch.py
  pool.py                 # durable data/state/candidate_pool.json
  review_queue.py         # durable data/state/research_review_queue.json
  source_quality.py       # SourceType / SourceTier
  freshness.py
  dedupe.py
  scoring.py              # discovery_score (research priority)
  fetch.py                # HTML → Playwright fallback
  pipeline.py
  cli.py
discover.py
config/source_queries.yaml
```

## Source Tier (research priority, not truth)

- **S**: government / exchange / official company disclosure / academic
- **A**: association / major media / authoritative research
- **B**: industry media / company news / technical sites
- **C**: vendor marketing / encyclopedia / aggregator / unknown

Wikipedia and vendor pages remain allowed as Candidates; they rank lower.

## Freshness

- Prefer real `published_at` from the fetched page
- Never copy `discovered_at` into `published_at`
- Unknown date → `published_at = null` and a safe mid/low freshness fallback
- Freshness affects ranking only (not REJECTED), unless a future query explicitly requires realtime events
- Query registry `intent`: `daily` / `insight` / `research` is Discovery intent only

## CLI

```bash
python discover.py --query "智能柜" --dry-run
python discover.py --topic smart-cabinet --dry-run
python discover.py --company "友宝" --dry-run
python discover.py --query "智能柜" --stage verify --limit 5
python discover.py --review-queue
python discover.py --review <id>
python discover.py --approve <id> --reason "worth research"
python discover.py --reject <id> --reason "noise"
python discover.py --defer <id> --reason "later"
```

## Hard rules

1. `snippet` / `provider_content` are discovery-only (never SourceDocument/Evidence bodies).
2. Candidate `VERIFIED` ≠ `ClaimStatus.VERIFIED` (claims stay draft).
3. Review Queue `APPROVED` ≠ publishable and does not auto-verify claims.
4. Publishing gate: non-bypassable `SEARCH_SNIPPET_AS_EVIDENCE` (`research/` must not import `publishing/`).
5. `ANYSEARCH_API_KEY` from env / `.env` only.
6. Do not wire AnySearch into `main.py` / `daily-crawl.yaml`.

## Durable state

- Candidate pool: `data/state/candidate_pool.json` (gitignored under `data/`)
- Research review queue: `data/state/research_review_queue.json` (same)

## Leftovers (out of v1.1)

- Auto topic/company scheduling in CI / daily-crawl
- Human Research Review → ClaimStatus.VERIFIED → Knowledge / Content
- Daily / Insight / WeChat / Website publish from Discovery
