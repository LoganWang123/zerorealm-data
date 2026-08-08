# Research Knowledge → Editorial Intake v1

**Date:** 2026-08-08  
**Branch:** `feature/research-knowledge-content-v1`  
**Status:** STOP before channel publish

## Five distinct concepts

| Concept | Meaning |
|---|---|
| **Candidate VERIFIED** | Source entered research evidence layer |
| **Claim VERIFIED** | Human fact verification passed |
| **Knowledge** | Reusable representation of verified claims |
| **Editorial APPROVED** | Human editorial review passed (expression / publish worthiness) |
| **READY_FOR_PUBLISH** | Package ready for channel publish — **not published yet** |

None of these auto-substitute for another.

## Pipeline

```text
Discovery / Registry
→ Evidence
→ Human Research Review
→ Verified Claim
→ Knowledge (active only)
→ Content Candidate
→ Editorial Brief / Internal Draft
→ Hard Gate
→ Human Editorial Review
→ Publish-Ready Package
→ STOP
```

Next stage (out of scope): Channel Publish (WeChat / Website).

## Hard rules

1. Only `ClaimStatus.VERIFIED` enters Knowledge.
2. Queue APPROVED / Candidate VERIFIED never enter Knowledge.
3. Daily: `primary_signal_count == 1`.
4. FACT statements require verified `claim_id`.
5. Hard Gate PASS is required before Editorial APPROVED.
6. Non-bypassable: UNSUPPORTED_FACT, SOURCE_LINEAGE_INCOMPLETE, FABRICATED_DATA, FUTURE_PUBLICATION, SEARCH_SNIPPET_AS_EVIDENCE, CLAIM_NOT_VERIFIED.
7. Internal drafts go to `dist/review/content/` only.
8. Package keeps `wechat_published=false` and `website_published=false`.

## CLI

```bash
python research_review.py --export-knowledge
python content_pipeline.py --build-candidates --type daily
python content_pipeline.py --list-candidates
python content_pipeline.py --show <id>
python content_pipeline.py --brief <id>
python content_pipeline.py --draft <id>
python content_pipeline.py --gate <id>
python content_pipeline.py --approve <id> --reviewer <name>
python content_pipeline.py --build-package <id>
```
