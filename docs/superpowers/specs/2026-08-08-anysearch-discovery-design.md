# AnySearch Source Discovery Design (v1 + v1.1)

**Date:** 2026-08-08  
**Branches:**  
- v1: `feature/anysearch-discovery-provider` (merged)  
- v1.1: `feature/discovery-quality-review-v1` (merged)  
- v1.2: `feature/discovery-evidence-quality-v12`  
**Status:** Discovery → Verify → Review Queue → Human Claim Review → Verified Research Output (no Daily/Publish)

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
  source_quality.py       # SourceType / SourceTier + config/source_quality.yaml
  publication_date.py     # date provenance (never invent crawl time)
  clustering.py           # syndication / secondary reports
  freshness.py
  dedupe.py
  scoring.py              # discovery_score (research priority)
  fetch.py                # HTML → Playwright fallback + diagnostics
  pipeline.py
  cli.py
research/
  atom_store.py           # durable Source/Evidence/Claim store
  claim_review.py         # explicit ClaimStatus transitions + audit log
  exporters/verified_research.py
research_review.py
discover.py
config/source_queries.yaml
config/source_quality.yaml
```

## Source Tier (research priority, not truth)

- **S**: government / exchange / official company disclosure / academic
- **A**: association / major media / authoritative research
- **B**: industry media / company news / technical sites
- **C**: vendor marketing / encyclopedia / aggregator / unknown

Wikipedia and vendor pages remain allowed as Candidates; they rank lower.

## Freshness / publication date

- Prefer real `published_at` from JSON-LD / meta / `<time>` / body patterns
- Store provenance: `published_at_source`, `published_at_confidence`, `modified_at`
- Never copy `discovered_at` / crawl time into `published_at`
- Unknown date → `published_at = null`
- Conflicts → keep priority winner + `PUBLICATION_DATE_CONFLICT` warning (not Evidence reject)

## Human Claim Review

```text
Queue APPROVED  ≠  ClaimStatus.VERIFIED
```

```bash
python research_review.py --claim <id>
python research_review.py --verify-claim <id> --reviewer <name> --reason "..."
python research_review.py --reject-claim <id> --reviewer <name> --reason "..."
python research_review.py --export-verified
```

Audit log: `data/state/research_review_log.jsonl` (append-only).
Verified export: `data/research/verified_claims.json` (runtime; not auto-publish).

## CLI

```bash
python discover.py --query "智能柜" --dry-run
python discover.py --topic smart-cabinet --dry-run
python discover.py --company "友宝" --dry-run
python discover.py --topics smart-cabinet,unmanned-retail --dry-run
python discover.py --run-registry --dry-run
python discover.py --query "智能柜" --stage verify --limit 5
python discover.py --review-queue
python discover.py --approve <id> --reason "worth research"
```

## Hard rules

1. `snippet` / `provider_content` are discovery-only (never SourceDocument/Evidence bodies).
2. Candidate `VERIFIED` ≠ `ClaimStatus.VERIFIED` (claims stay draft until explicit human review).
3. Review Queue `APPROVED` ≠ ClaimStatus.VERIFIED and does not auto-verify claims.
4. Publishing gate: non-bypassable `SEARCH_SNIPPET_AS_EVIDENCE` (`research/` must not import `publishing/`).
5. `ANYSEARCH_API_KEY` from env / `.env` only.
6. Do not wire AnySearch into `main.py` / `daily-crawl.yaml`.
7. GitHub Actions Discovery smoke is `workflow_dispatch` only; scheduled Discovery blocked by ephemeral runner state.

## Durable state

- Candidate pool: `data/state/candidate_pool.json`
- Research review queue: `data/state/research_review_queue.json`
- Research atoms: `data/state/research_atoms.json`
- Review audit log: `data/state/research_review_log.jsonl`

## Leftovers

- Durable CI/runner storage for scheduled Discovery
- Human Review → Knowledge / Content production wiring
- Daily / Insight / WeChat / Website publish from Discovery
