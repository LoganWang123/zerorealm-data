# Content Production v1: Controlled Generation and Channel Release Candidate

**Date:** 2026-08-08  
**Branch:** `feature/content-production-v1`  
**Status:** STOP at READY_FOR_CHANNEL_REVIEW (no publish)

## Pipeline

```text
Verified Claim → Knowledge → Content Candidate → Editorial Brief
→ Allowed Facts → Controlled Generator → Structured Draft
→ Post-generation Audit → Hard Gate → Bounded Repair (≤2)
→ Human Editorial APPROVED → Website/WeChat Preview Render
→ Channel Consistency → Release Candidate (READY_FOR_CHANNEL_REVIEW)
→ STOP
```

## Hard rules

1. Generator context = Allowed Facts only (VERIFIED claims).
2. Post-generation audit is mandatory and independent of the model.
3. Repair max 2; cannot add claims/numbers/sources.
4. Editorial cannot bypass Hard Gate FAIL.
5. Renderers never call publishers.
6. Publisher requires READY_FOR_PUBLISH; this round ends at READY_FOR_CHANNEL_REVIEW → CHANNEL_REVIEW_REQUIRED.
