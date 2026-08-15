# Publication Safety & State Integrity Implementation Plan

> **For agentic workers:** Execute **inline / sequentially in one session**. Do **not** use subagents. Do **not** use subagent-driven-development. Checkpoints via STOP/REVIEW only.
>
> **Design spec:** `docs/plans/2026-08-08-publication-safety-design.md`
>
> **Global execution constraints (read first):**
> - Model: **Auto only**
> - **Inline / sequential.** Workstream A (website P0) first. Workstream B starts **only after human acceptance of A**.
> - **No commit / push / merge / deploy / Editorial APPROVE / Channel APPROVE / WeChat broadcast / Zhihu publish** without explicit human approval
> - Do **not** assume PR #15 (`zerorealm-data` `feature/deepseek-content-quality-v1`) is merged
> - Do **not** modify, delete, or “clean up” known dirty/untracked files beyond the intentional edits listed in this plan
> - Do **not** raw-delete `data/state/research_atoms.json` or `research_review_queue.json` — quarantine by move only in Workstream B (CEO-approved after A acceptance)
> - Do **not** touch `seen_ids.json`
> - Do **not** add or change `gate_status` / `hard_gate_status` on `smart-cabinet-five-process-metrics` or either scheduled P0 Insight
> - Prefer isolated git worktrees for code changes so primary dirty checkouts stay untouched (create them only when executing, not during doc-only revisions)

**Goal:** Prevent two scheduled website Insights from auto-publishing on 2026-09-02/03; after A acceptance, quarantine contaminated discovery runtime state safely and stop tests from writing fixture data into production-like `data/state` paths—without touching PR #15 scope.

**Architecture:** Sequenced hotfixes. (A) `zerorealm-website`: content freeze + eligibility so `scheduled` is always non-public and Insights need explicit `status: published` (missing gate OK; rejecting gate blocks). (B, after A acceptance) `zerorealm-data`: reversible quarantine of the two contaminated ignored JSON files + AST (or equivalent) guard that fails until all `persist=True` discovery tests isolate `pool_path` / `queue_path` / `atoms_path`. Planning docs live in `zerorealm-data/docs/plans/`.

**Tech Stack:** Next.js / Node test runner (`node:test`) on website; Python / pytest on data; git worktrees optional; PowerShell on Windows.

## Global Constraints

- Workspace root: `D:\soft\AI\ZeroRealmAI`
- Website repo: `D:\soft\AI\ZeroRealmAI\zerorealm-website` — base `main`
- Data repo: `D:\soft\AI\ZeroRealmAI\zerorealm-data` — base `master` (not PR #15 head for new commits)
- PR #15 remains OPEN and untouched
- Preserve untracked files exactly (covers, publish yamls, tmp trees, `pr-*-create-ready.md`, website `scene-01.mp4.partial`, etc.)
- Every high-impact action stops for human review
- **No parallel A+B.** No subagents.

---

## File map (planned code changes — not done in planning task)

### Website (`zerorealm-website`) — Workstream A

| Path | Responsibility |
|---|---|
| `lib/publish-eligibility.ts` | Add `scheduled` to non-public; Insight requires `status: published`; rejecting gates hide; missing gate on published Insight remains eligible |
| `content/insight/smart-cabinet-2026-operations.mdx` | Content freeze (`visibility: private`); keep `scheduled`; **no gate fields** |
| `content/insight/instant-retail-policy-2026.mdx` | Content freeze (`visibility: private`); keep `scheduled`; **no gate fields** |
| `tests/publish-eligibility.test.ts` | Fix scheduled assertion; Sep 2/3 proofs; published+missing-gate eligible; rejecting gate ineligible |
| `tests/editorial-gate-hotfix.test.ts` | Align Insight expectations with new rule (no required passing gate) |
| `tests/insight-search-index.test.ts` | Assert P0 slugs absent; five-process-metrics still present without adding a gate |

### Data (`zerorealm-data`) — Workstream B only after A acceptance

| Path | Responsibility |
|---|---|
| `tests/test_discovery_pipeline.py` | Isolate atoms/queue/pool paths in all `persist=True` tests |
| `tests/test_discovery_quality_review.py` | Pass `pool_path`, `queue_path`, `atoms_path` (and stores) on all persist runs |
| `tests/test_runtime_state_isolation.py` (create) | **Red-first AST (or equivalent) guard** that fails on leaking constructors; optional secondary safe-pipeline check |
| `data/state/_quarantine/<ts>/` (runtime, ignored) | Backup destination for the two contaminated JSON files only |

**Do not modify:** `content/insight/smart-cabinet-five-process-metrics.mdx` gate fields; `seen_ids.json`.

---

## Branch / worktree strategy (do this before code edits — Workstream A only at start)

### Task 0: Create isolated worktree for website (no commits)

**Repos:** `zerorealm-website` first  
**Does not modify:** PR #15 branch contents  
**Defer:** data worktree until Workstream B (after A acceptance)

- [ ] **Step 0.1: Record dirty baselines (read-only)**

Run in website:

```powershell
cd D:\soft\AI\ZeroRealmAI\zerorealm-website
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
```

Run in data (baseline only; no B edits yet):

```powershell
cd D:\soft\AI\ZeroRealmAI\zerorealm-data
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
gh pr view 15 --json state,headRefName,baseRefName,url
```

Expected: known untracked lists unchanged; PR #15 `OPEN` on `feature/deepseek-content-quality-v1`.

- [ ] **Step 0.2: Create website hotfix worktree from `main`**

```powershell
cd D:\soft\AI\ZeroRealmAI\zerorealm-website
git fetch origin
git worktree add D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-website-insight-sched-gate -b hotfix/insight-scheduled-publish-gate-20260808 origin/main
```

Expected: new worktree on new branch from current `origin/main`.

- [ ] **STOP / REVIEW 0:** Human confirms website worktree exists and primary dirty trees were not cleaned. Proceed to Workstream A only.

---

## Workstream A — Website publication safety (test-first; P0)

### Task 1: Failing eligibility tests for scheduled Insights

**Repo:** `zerorealm-website` (worktree `...\zerorealm-website-insight-sched-gate`)  
**Files:**
- Modify: `tests/publish-eligibility.test.ts`
- Modify: `tests/editorial-gate-hotfix.test.ts` (only if assertions conflict after Task 2; prepare expectations here)

**Interfaces:**
- Consumes: `isPubliclyPublished`, `isPublicContentEligible`, `isProductionPublicEligible`, `shanghaiToday` from `lib/publish-eligibility.ts`
- Produces: regression covering Sep 2/3 + `scheduled` never public + Insight publish semantics

- [ ] **Step 1.1: Write / replace failing assertions**

In `tests/publish-eligibility.test.ts`:

1. Change the assertion that currently expects:

```ts
isPubliclyPublished(
  { date: "2026-08-08", status: "scheduled", visibility: "public" },
  now
) === true
```

to expect `false`.

2. Add a new test (exact intent):

```ts
test("scheduled insights stay non-public on their publication day without human approval", () => {
  const ops = loadInsightFrontmatter("smart-cabinet-2026-operations.mdx");
  const policy = loadInsightFrontmatter("instant-retail-policy-2026.mdx");

  const dayOps = new Date("2026-09-02T12:00:00+08:00");
  const dayPolicy = new Date("2026-09-03T12:00:00+08:00");

  assert.equal(ops.status, "scheduled");
  assert.equal(policy.status, "scheduled");

  assert.equal(isPubliclyPublished(ops, dayOps), false);
  assert.equal(isPublicContentEligible(ops, dayOps), false);
  assert.equal(isPubliclyPublished(policy, dayPolicy), false);
  assert.equal(isPublicContentEligible(policy, dayPolicy), false);

  // Even if visibility were left public, scheduled must not flip public by date alone.
  assert.equal(
    isPubliclyPublished(
      { date: "2026-09-02", status: "scheduled", visibility: "public", type: "observation" },
      dayOps
    ),
    false
  );
});
```

3. Add proof of explicit human publish path (published + public; **missing gate allowed**; rejecting gate blocks):

```ts
test("insight becomes public when explicitly published; missing gate allowed; rejecting gate blocks", () => {
  const now = new Date("2026-09-02T12:00:00+08:00");

  // status=published + visibility=public + no gate → eligible (backward compatibility)
  assert.equal(
    isPublicContentEligible(
      {
        date: "2026-09-02",
        status: "published",
        visibility: "public",
        type: "observation",
      },
      now
    ),
    true
  );

  // explicit rejecting gate → ineligible
  assert.equal(
    isPublicContentEligible(
      {
        date: "2026-09-02",
        status: "published",
        visibility: "public",
        type: "observation",
        gate_status: "rejected",
      },
      now
    ),
    false
  );

  // non-published status → ineligible even with public visibility
  assert.equal(
    isPublicContentEligible(
      {
        date: "2026-09-02",
        status: "scheduled",
        visibility: "public",
        type: "observation",
      },
      now
    ),
    false
  );
});
```

**Do not** assert that Insight requires `gate_status: "passed"`.  
**Do not** add tests that require writing gates onto existing MDX files.

Import `isPublicContentEligible` if not already imported.

- [ ] **Step 1.2: Run targeted tests — expect FAIL**

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-website-insight-sched-gate
node --test tests/publish-eligibility.test.ts
```

Expected: FAIL on the new scheduled-day assertions and/or the flipped scheduled assertion (current code still auto-publics `scheduled` when date ≤ today).

- [ ] **STOP / REVIEW 1:** Confirm failures match the design (auto-publish of `scheduled`), not unrelated fixture breakage.

---

### Task 2: Implement eligibility fix + content freeze

**Repo:** `zerorealm-website` worktree  
**Files:**
- Modify: `lib/publish-eligibility.ts`
- Modify: `content/insight/smart-cabinet-2026-operations.mdx`
- Modify: `content/insight/instant-retail-policy-2026.mdx`
- Modify: `tests/editorial-gate-hotfix.test.ts` as needed

**Interfaces:**
- Produces: `scheduled` ∈ non-public; Insight public requires `status === "published"`; rejecting/failed/blocked gate → ineligible; **missing gate on published Insight remains eligible**

- [ ] **Step 2.1: Minimal eligibility implementation**

In `lib/publish-eligibility.ts`:

1. Add `"scheduled"` to `NON_PUBLIC_STATUSES`.
2. Update `isPublicContentEligible` non-daily branch so that after the existing rejection check:

```ts
  // non-daily (Insight / observation / etc.)
  // Require explicit status=published. Missing gate is allowed (backward compatibility).
  // Do NOT treat missing gate as Editorial APPROVE. Do NOT require a passing gate.
  const status = String(content.status || "").toLowerCase();
  return status === "published";
```

3. Keep Daily branch unchanged (still requires explicit passing hard gate).
4. Update comments: remove any implication that Insight must have a passing gate; document that missing gate ≠ APPROVE.

**Hard constraints for this hotfix:**

- Do **not** add `gate_status` / `hard_gate_status` to `smart-cabinet-five-process-metrics.mdx`.
- Do **not** add or change gate fields on either scheduled P0 file.
- Do **not** require a passing gate for Insight eligibility.
- Already-public five-process-metrics must remain eligible via `status: published` + missing gate.

- [ ] **Step 2.2: Content freeze the two P0 files**

In both:

- `content/insight/smart-cabinet-2026-operations.mdx`
- `content/insight/instant-retail-policy-2026.mdx`

Change:

```yaml
visibility: "public"
```

to:

```yaml
visibility: "private"
```

Keep `status: "scheduled"`. Do **not** set or add any `gate_status` / `hard_gate_status`.

- [ ] **Step 2.3: Update editorial-gate Insight test**

In `tests/editorial-gate-hotfix.test.ts`, align observation/Insight cases with:

- `status: "published"` + no gate → eligible (if date/visibility allow)
- `status: "scheduled"` → ineligible regardless of date
- rejecting/failed/blocked gate → ineligible
- Daily still requires passing hard gate

Do **not** require `gate_status: "passed"` for Insight eligibility assertions.

- [ ] **Step 2.4: Run targeted tests — expect PASS**

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-website-insight-sched-gate
node --test tests/publish-eligibility.test.ts tests/editorial-gate-hotfix.test.ts tests/insight-search-index.test.ts tests/content-type-isolation.test.ts
```

Expected: PASS. Search index still includes five-process-metrics (unchanged gate fields); excludes the two P0 slugs.

- [ ] **STOP / REVIEW 2:** Human reviews eligibility semantics + MDX freeze diff. **No commit unless human asks.**

---

### Task 3: Website full verification + future-date proof + A acceptance gate

**Repo:** `zerorealm-website` worktree

- [ ] **Step 3.1: Full relevant test suite**

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-website-insight-sched-gate
npm test
```

If project uses a different script, use `package.json` test script as source of truth (`npm run test` / `node --test tests/**/*.test.ts`). Expected: all green.

- [ ] **Step 3.2: Explicit future-date proof script (read-only one-liner)**

```powershell
node --input-type=module -e "import { isPublicContentEligible } from './lib/publish-eligibility.ts'; import fs from 'fs'; import matter from 'gray-matter'; const load=f=>matter(fs.readFileSync('content/insight/'+f,'utf8')).data; const ops=load('smart-cabinet-2026-operations.mdx'); const pol=load('instant-retail-policy-2026.mdx'); const a=new Date('2026-09-02T12:00:00+08:00'); const b=new Date('2026-09-03T12:00:00+08:00'); console.log({ops:isPublicContentEligible(ops,a), pol:isPublicContentEligible(pol,b), opsVis:ops.visibility, polVis:pol.visibility, opsStatus:ops.status, polStatus:pol.status});"
```

Expected stdout includes `ops: false`, `pol: false`, visibilities `private`, statuses `scheduled`.

- [ ] **Step 3.3: Build check**

```powershell
npm run build
```

Expected: success (or document known env-only failures without claiming success).

- [ ] **Step 3.4: Diff / status hygiene**

```powershell
git status --short
git diff --stat
```

Expected: only eligibility, tests, and the two P0 Insight frontmatter visibility changes. No gate-field edits on any Insight. No unrelated untracked deletions.

- [ ] **STOP / REVIEW 3 — Workstream A acceptance:** Human decides whether to commit/push/open PR and whether A is **accepted**. Agent must not merge or deploy. **Do not start Workstream B until human explicitly accepts A.**

**Human Insight publish path (document in report; do not auto-perform):**

1. Reviewed content change: set `status: published` and `visibility: public`.
2. If a rejecting gate exists, resolve it manually.
3. Human merge → human production deploy.

---

## Workstream B — Data runtime-state integrity (test-first; only after A acceptance; not PR #15)

**Prerequisite:** Workstream A human-accepted.  
**CEO quarantine approval:** Quarantine of the two contaminated JSON files is approved for this workstream after A acceptance. Still never delete; still leave `seen_ids.json` untouched.

### Task 0b: Create data hotfix worktree (after A acceptance)

- [ ] **Step 0b.1: Create data worktree from `master` (not PR #15)**

```powershell
cd D:\soft\AI\ZeroRealmAI\zerorealm-data
git fetch origin
git worktree add D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-data-state-isolation -b hotfix/runtime-state-test-isolation-20260808 origin/master
```

Expected: new branch from `origin/master`. Confirm:

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-data-state-isolation
git rev-parse --abbrev-ref HEAD
git merge-base --is-ancestor origin/feature/deepseek-content-quality-v1 HEAD; echo "exit=$LASTEXITCODE"
```

Note: PR #15 tip may not be ancestor of this hotfix (expected). Hotfix must not check out `feature/deepseek-content-quality-v1` for edits.

- [ ] **STOP / REVIEW 0b:** Human confirms data worktree exists; primary dirty tree untouched.

---

### Task 4: Quarantine contaminated runtime state (CEO-approved after A; reversible)

**Repo:** primary `zerorealm-data` checkout **or** data worktree that can see the same ignored `data/state` files  
**Important:** Ignored files may exist only in the primary working tree. Quarantine where the contaminated files actually live:  
`D:\soft\AI\ZeroRealmAI\zerorealm-data\data\state\`

- [ ] **Step 4.1: Snapshot evidence before move**

```powershell
cd D:\soft\AI\ZeroRealmAI\zerorealm-data
python -c "from pathlib import Path; import hashlib, json; 
for name in ['research_atoms.json','research_review_queue.json']:
 p=Path('data/state')/name
 print(name, 'exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
 if p.exists():
  h=hashlib.sha256(p.read_bytes()).hexdigest(); d=json.loads(p.read_text(encoding='utf-8'))
  print(' sha256', h); print(' updated_at', d.get('updated_at'))"
```

Expected: atoms ~4854 bytes; queue ~861 bytes; `updated_at` `2026-08-08T22:22:23+08:00`; fake/example.com markers. Record hashes/size/`updated_at` in the execution report.

- [ ] **Step 4.2: Move into quarantine (never delete)**

```powershell
$ts = "2026-08-08T222223"
$dest = "data/state/_quarantine/$ts"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Move-Item data/state/research_atoms.json "$dest/research_atoms.json"
Move-Item data/state/research_review_queue.json "$dest/research_review_queue.json"
Get-ChildItem $dest
```

Expected: both files present under quarantine; active paths for those two files absent. **Do not move or modify `seen_ids.json`.**

- [ ] **Step 4.3: Verify destination + prove restore path**

Verify destination listing and sizes match snapshot. Document restore (do not necessarily run restore):

```powershell
Move-Item "data/state/_quarantine/2026-08-08T222223/research_atoms.json" data/state/research_atoms.json
Move-Item "data/state/_quarantine/2026-08-08T222223/research_review_queue.json" data/state/research_review_queue.json
```

- [ ] **STOP / REVIEW 4:** Human confirms quarantine complete; `seen_ids.json` left as-is.

---

### Task 5: Red-first isolation guard (must FAIL on current callers)

**Repo:** `zerorealm-data` worktree `...\zerorealm-data-state-isolation`  
**Files:**
- Create: `tests/test_runtime_state_isolation.py`

**Quality bar (CEO):** The first new guard must **FAIL** against the current leaking test constructors and **PASS only after** all `persist=True` discovery tests explicitly set `pool_path`, `queue_path`, and `atoms_path` under `tmp_path`. A static AST-based scan over relevant discovery test files is acceptable. A safe-pipeline test that already passes before fixing callers is **not** sufficient as the red test.

- [ ] **Step 5.1: Write the failing AST (or equivalent) guard**

Create `tests/test_runtime_state_isolation.py` that:

1. Parses relevant discovery test modules with the AST (at minimum):
   - `tests/test_discovery_pipeline.py`
   - `tests/test_discovery_quality_review.py`
2. Finds constructions equivalent to `DiscoveryPipelineConfig(... persist=True ...)` (and/or `DiscoveryPipeline` setups that persist).
3. Fails unless **every** such construction also supplies explicit `pool_path`, `queue_path`, and `atoms_path` (string/keyword args or clearly bound locals under `tmp_path` — implement the check so current leaking callers fail today).
4. Optionally (secondary only): a safe-pipeline smoke that runs with all three tmp paths and asserts default `data/state/research_*.json` are untouched — this must **not** be the sole red test.

Characterization of production defaults may remain as documentation, but it is not the red gate.

- [ ] **Step 5.2: Run — expect FAIL (red)**

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-data-state-isolation
pytest tests/test_runtime_state_isolation.py -v
```

Expected: the AST/isolation guard **FAILS** because current callers omit one or more of `atoms_path` / `queue_path` / `pool_path` under `tmp_path`.

- [ ] **STOP / REVIEW 5:** Confirm the failure is the intended leaking-constructor signal, and that the test itself does not write to production state.

---

### Task 6: Fix discovery tests to isolate all durable paths (make the guard green)

**Repo:** `zerorealm-data` worktree  
**Files:**
- Modify: `tests/test_discovery_pipeline.py`
- Modify: `tests/test_discovery_quality_review.py`
- Optionally small helper in the same test modules (avoid production code change unless needed)

**Interfaces:**
- Consumes: `DiscoveryPipeline`, `DiscoveryPipelineConfig`, `ResearchAtomStore`, `ResearchReviewQueue`, `CandidatePool`
- Produces: every `persist=True` construction sets `pool_path`, `queue_path`, `atoms_path` under `tmp_path`

- [ ] **Step 6.1: Fix `test_durable_pool_reuses_canonical_url`**

Replace configs with:

```python
atoms_path = tmp_path / "atoms.json"
queue_path = tmp_path / "queue.json"
config=DiscoveryPipelineConfig(
    persist=True,
    pool_path=str(pool_path),
    queue_path=str(queue_path),
    atoms_path=str(atoms_path),
)
# and pass atom_store=ResearchAtomStore(atoms_path), review_queue=ResearchReviewQueue(queue_path)
```

Apply to both `pipe1` and `pipe2`.

- [ ] **Step 6.2: Fix `test_discovery_quality_review.py` persist=True cases**

For each `DiscoveryPipelineConfig(persist=True, ...)` that omits any of the three paths, add:

```python
atoms_path = tmp_path / "atoms.json"
# ...
atom_store=ResearchAtomStore(atoms_path),
config=DiscoveryPipelineConfig(
    persist=True,
    pool_path=str(pool_path),
    queue_path=str(queue_path),
    atoms_path=str(atoms_path),
),
```

- [ ] **Step 6.3: Strengthen `_pipeline` helper (optional but recommended)**

In `test_discovery_pipeline.py` `_pipeline`, when `tmp_path` is provided, also set `queue_path` and `atoms_path` under `tmp_path` even if `persist=False`, and pass isolated store objects—so accidental `persist=True` overrides cannot hit defaults.

- [ ] **Step 6.4: Run isolation guard + discovery tests — expect PASS**

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-data-state-isolation
pytest tests/test_runtime_state_isolation.py tests/test_discovery_pipeline.py tests/test_discovery_quality_review.py tests/test_discovery_v12.py -v
```

Expected: AST guard now **PASS**; discovery suites PASS; no new files under primary `data/state` defaults inside the worktree.

- [ ] **STOP / REVIEW 6:** Human reviews test-only diff. Confirm PR #15 branch still untouched (`git status` on primary `feature/deepseek-content-quality-v1` checkout).

---

### Task 7: Data full verification

**Repo:** `zerorealm-data` worktree

- [ ] **Step 7.1: Lint + full pytest**

```powershell
cd D:\soft\AI\ZeroRealmAI\.worktrees\zerorealm-data-state-isolation
ruff check .
pytest
```

Expected: ruff clean; pytest green (count ≥ prior baseline on this branch; do not require PR #15 tests if not present on `master` base).

- [ ] **Step 7.2: Prove default state untouched by test run**

```powershell
python -c "from pathlib import Path; p=Path('data/state');
print('atoms', (p/'research_atoms.json').exists());
print('queue', (p/'research_review_queue.json').exists());
print('seen_ids', (p/'seen_ids.json').exists());
print('quarantine', (p/'_quarantine').exists())"
```

In worktree: expect atoms/queue active paths False unless copied. In primary tree after quarantine: those two active files absent; quarantine present; `seen_ids.json` still present if it was before.

- [ ] **Step 7.3: Diff / status**

```powershell
git status --short
git diff --stat
```

Expected: only test files (+ optional tiny helper). No PR #15 quality modules. No force-add of `data/state`.

- [ ] **STOP / REVIEW 7:** Human decides commit/push/PR. **Do not merge.** Leave PR #15 as-is.

---

## Task 8: Final Cursor execution report (mandatory format)

After Workstream A (and B only if A was accepted and B ran), the implementer writes a report to the user (and optionally `docs/reports/` **only if human asks**). Use this exact structure:

```markdown
# Publication Safety Execution Report — YYYY-MM-DD

## Model
- Auto only: YES/NO
- Inline sequential (no subagents): YES/NO

## Actions NOT taken (must remain true unless human approved)
- commit: NO
- push: NO
- merge: NO
- production deploy: NO
- Editorial/Channel APPROVE: NO
- WeChat broadcast: NO
- Zhihu publishing: NO
- gate_status written onto existing Insight content: NO

## Sequencing
- Workstream A accepted before B started: YES/NO/N/A

## PR #15
- state: OPEN/… 
- modified by this work: NO (required)

## Website hotfix
- branch/worktree:
- files changed:
- targeted tests + outcome:
- full suite + outcome:
- Sep 2/3 eligibility proof output:
- gate fields unchanged on five-process-metrics + two scheduled files: YES/NO
- git status/diff summary:

## Data hotfix (only if A accepted)
- branch/worktree:
- quarantine path + sha256/size/updated_at before move:
- seen_ids.json untouched: YES/NO
- AST isolation guard red-then-green: YES/NO
- files changed:
- pytest subsets + full suite outcomes:
- proof defaults untouched:
- git status/diff summary:

## Dirty file preservation
- zerorealm-data untracked still present: YES/NO
- zerorealm-website untracked still present: YES/NO

## Blockers / residual risk
- …
```

- [ ] **Step 8.1: Emit report to human**
- [ ] **STOP / REVIEW 8:** Await human merge/deploy decisions.

---

## Commit messaging (only if human explicitly requests commits)

Website (example):

```text
fix(editorial): keep scheduled Insights non-public without human approval

Prevent calendar auto-publish for scheduled observation content and freeze
the Sep 2/3 Insight drafts behind private visibility. Insight public paths
require explicit status=published; missing gate stays backward-compatible.
```

Data (example):

```text
test(discovery): isolate durable atom and review-queue paths

Stop persist=True discovery fixtures from writing into data/state defaults.
Add an AST guard that fails unless pool/queue/atoms paths are isolated.
```

Do **not** include quarantine JSON in commits.

---

## Spec coverage checklist (self-review)

| Design requirement | Task |
|---|---|
| Prevent Sep 2/3 auto-public; `scheduled` always non-public | Tasks 1–3 |
| Visibility private on two P0 files; remain scheduled; no gate edits | Task 2.2 |
| Insight requires `status=published`; rejecting gate blocks; missing gate OK | Tasks 1.1, 2.1 |
| Daily hard gate unchanged | Task 2.1 |
| No `gate_status: passed` on existing content | Tasks 2, 9.1 |
| Human publish path; merge/deploy manual | Task 3 STOP |
| Quarantine two JSON after A acceptance; never delete; `seen_ids` untouched | Task 4 |
| AST red-first isolation guard; fix callers; then green | Tasks 5–6 |
| Preserve PR #15 scope | Task 0/0b, 6 STOP, 8 |
| Inline sequential; A then B | Global constraints |
| Final report format | Task 8 |

---

## Execution choice (CEO-locked)

Plan revised and saved to `docs/plans/2026-08-08-publication-safety-and-state-integrity.md`.

**Locked by CEO:**

1. **Inline Execution** — same session, sequential checkpoints. **No subagents.**
2. **Workstream A (website P0) first.** Workstream B starts only after A acceptance.
3. Quarantine in B is CEO-approved after A acceptance (snapshot → move two JSON → verify → restore docs; never delete; leave `seen_ids.json`).

Do not begin implementation until the human asks to execute.
