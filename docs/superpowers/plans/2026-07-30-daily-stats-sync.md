# Daily Stats Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the website's published daily-report count synchronized whenever the data workflow adds a report.

**Architecture:** The daily GitHub Actions job already copies a generated MDX report into the checked-out website repository. Immediately after that copy, a small Python step will count `content/daily/*.mdx` and write the count into `data/stats.json`. The same commit will include both files.

**Tech Stack:** GitHub Actions, Python 3.11, JSON, Node.js test runner.

## Global Constraints

- Preserve the workflow's existing report-generation and website-sync behavior.
- Do not add dependencies.
- Do not change official-account publishing behavior.
- `dailyIssues` must equal the count of deployed `content/daily/*.mdx` files.

---

### Task 1: Synchronize the visible count and automate future updates

**Files:**
- Modify: `.github/workflows/daily-crawl.yaml`
- Modify: `../zerorealm-website/data/stats.json`
- Test: `../zerorealm-website/tests/stats.test.ts`

**Interfaces:**
- Consumes: `website/content/daily/*.mdx` after the report copy step.
- Produces: `website/data/stats.json` with an integer `dailyIssues` equal to the MDX file count.

- [ ] **Step 1: Use the existing failing consistency test**

Run: `npm test`

Expected: `published content counts match the files shipped by the website` fails because `dailyIssues` is 1 while three MDX files exist.

- [ ] **Step 2: Add the minimal workflow update**

After copying the report, run:

```bash
python - <<'PY'
import json
from pathlib import Path

stats_path = Path("website/data/stats.json")
stats = json.loads(stats_path.read_text(encoding="utf-8"))
stats["dailyIssues"] = len(list(Path("website/content/daily").glob("*.mdx")))
stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

Stage both `content/daily/${DATE}.mdx` and `data/stats.json` before committing.

- [ ] **Step 3: Correct the current website data**

Set `data/stats.json` field `dailyIssues` to `3`, matching the three shipped daily MDX files.

- [ ] **Step 4: Verify green**

Run: `npm test && npm run build`

Expected: all tests pass and the production build succeeds.

- [ ] **Step 5: Commit and push the data-workflow and website changes**

Create focused commits using the configured personal Git identity, then push the updated `master` and `main` branches without force-pushing.
