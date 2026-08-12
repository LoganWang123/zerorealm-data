# Publication Safety & Runtime State Integrity — Design

**Date:** 2026-08-08  
**Status:** Design revised per CEO decisions (2026-08-08 evening) — ready for inline sequential execution  
**Model constraint:** Cursor CLI / Auto only  
**Execution mode:** Inline / sequential in one session. **No subagents.**  
**Scope of this document:** Design only. No code, merge, deploy, or channel publish while revising docs.

---

## 1. Context

CEO direction (Route A): **safety closure first**, then a two-week growth experiment. Immediate P0 is preventing accidental public exposure and preventing fixture/runtime contamination—not growth features.

Two risk surfaces, **sequenced** (not parallel):

| Order | Surface | Repository | Risk |
|---|---|---|---|
| **A first (P0)** | Website publication safety | `zerorealm-website` | Two scheduled Insight MDX files become public on 2026-09-02 / 2026-09-03 without human approval |
| **B after A acceptance** | Data runtime-state integrity | `zerorealm-data` | Ignored `data/state/*.json` contaminated by fake discovery fixtures; future tests can overwrite production-like state |

**Workstream B must not start until Workstream A is human-accepted.**

High-impact actions remain **manual only**: merge, production deploy, Editorial/Channel APPROVE, WeChat broadcast, Zhihu publishing.

---

## 2. Verified current behavior (read-only inspection 2026-08-08)

### 2.1 Website — publication eligibility

**Source of truth:** `zerorealm-website/lib/publish-eligibility.ts`

Observed rules:

1. `NON_PUBLIC_STATUSES` includes `draft`, `unpublished`, `reviewing`, `pending`, `pending_verification`, `preview`, `review`, `withdrawn` — **does not include `scheduled`**.
2. `isPubliclyPublished`:
   - treats missing status as `"published"`;
   - allows any status not in `NON_PUBLIC_STATUSES` (including `scheduled`);
   - becomes true when `date`/`publishedAt` ≤ Asia/Shanghai today and visibility ≠ private.
3. Existing unit test **encodes this auto-publish behavior**:

```ts
// tests/publish-eligibility.test.ts
isPubliclyPublished(
  { date: "2026-08-08", status: "scheduled", visibility: "public" },
  now
) === true
```

4. `isPublicContentEligible`:
   - Daily (`type === "daily"` or missing type defaulting to daily): requires explicit hard-gate pass (`passed` / `pass` / `passed_with_edit`).
   - Non-daily (Insight / `observation`): **missing `gate_status` remains eligible** if not explicitly rejected.
5. Public Insight surfaces (`lib/mdx.ts` `getAllInsights` / `getInsightBySlug`) use `isProductionPublicEligible` → `isPublicContentEligible`.

### 2.2 Website — the two at-risk Insight files

| File | Frontmatter (verified) |
|---|---|
| `content/insight/smart-cabinet-2026-operations.mdx` | `date: "2026-09-02"`, `type: "observation"`, `status: "scheduled"`, `visibility: "public"`, **no** `gate_status` / `hard_gate_status` |
| `content/insight/instant-retail-policy-2026.mdx` | `date: "2026-09-03"`, `type: "observation"`, `status: "scheduled"`, `visibility: "public"`, **no** `gate_status` / `hard_gate_status` |

Today (2026-08-08) they are hidden only because publication day is still in the future. On Shanghai calendar 2026-09-02 / 2026-09-03 they become public **without any human gate**.

Contrast: `content/insight/smart-cabinet-five-process-metrics.mdx` is already `status: "published"` and is intentionally public. **Do not add or change** `gate_status` / `hard_gate_status` on this file or on either scheduled P0 file.

### 2.3 Data — runtime state (ignored, must not be deleted in planning)

`.gitignore` rule `data/*` ignores:

- `data/state/research_atoms.json`
- `data/state/research_review_queue.json`
- `data/state/seen_ids.json`

**Observed `research_atoms.json` (2026-08-08):**

- `updated_at`: `2026-08-08T22:22:23+08:00`
- 3 sources, 3 evidence, 3 claims
- All claim statuses: `draft` (0 `VERIFIED`)
- Sources include `https://www.example.com/story`, `https://example.com/story`, `https://www.caixin.com/2026/a.html`
- `discovery_provider`: `fake` on all inspected sources
- File bytes are valid UTF-8 Chinese; some Windows consoles display them as mojibake (codepage display issue). Content text matches discovery test fixtures (e.g. durable-pool body starting with 「足够长的正文…」).

**Observed `research_review_queue.json`:**

- Same `updated_at`: `2026-08-08T22:22:23+08:00`
- 1 item, `review_status: PENDING`, `provider: fake`, `url: https://example.com/story`

`seen_ids.json` is **untouched** by quarantine (leave in place).

### 2.4 Data — contamination root cause (code-backed)

`DiscoveryPipelineConfig` defaults:

- `persist: True`
- `pool_path` → `data/state/candidate_pool.json`
- `queue_path` → `data/state/research_review_queue.json`
- `atoms_path` → `data/state/research_atoms.json`

Verified leaking tests:

1. `tests/test_discovery_pipeline.py` :: `test_durable_pool_reuses_canonical_url`  
   - `persist=True`, overrides **only** `pool_path`  
   - Leaves default `atoms_path` + `queue_path` → writes fake provider data into runtime state  
   - Fixture URL `https://www.example.com/story`, title `"t"`, body 「足够长的正文用于验证候选持久化与再次发现。」 match observed atoms.

2. `tests/test_discovery_quality_review.py` (several cases with `persist=True`)  
   - Often set `queue_path` to `tmp_path` but **omit `atoms_path` / `atom_store`**  
   - Still persists atoms to the default production-like path.

`persist=False` avoids disk save at the end of a run, but any `persist=True` path that omits isolated atoms/queue paths is unsafe.

PR #15 (`feature/deepseek-content-quality-v1`) does **not** fix this; its tests generally use `tmp_path` atom stores. Shadow script reads production atoms but writes ephemeral artifacts when verified claims are absent.

### 2.5 PR #15 status (zerorealm-data)

- **OPEN**, base `master`, head `feature/deepseek-content-quality-v1`
- CI validate: SUCCESS / MERGEABLE
- Scope: DeepSeek content quality evaluator, shadow production, prompt fixtures — **not** publication eligibility, **not** discovery state isolation
- Must not be expanded with unrelated safety work that delays or muddies review

Website has no PR #15; website `main` is at merge of Insight search index (#7). Editorial hard-gate for Daily already landed via prior hotfixes.

---

## 3. Safety invariants

### 3.1 Website publication invariants

1. **`status: scheduled` is always non-public**, regardless of calendar date.
2. The two P0 Insight files change `visibility: public` → `private` and **remain** `status: scheduled`.
3. **Non-daily / Insight public eligibility** requires explicit `status: published` (plus date/visibility rules via `isPubliclyPublished`).
4. An explicit **rejected / failed / blocked** gate still makes content ineligible.
5. A **missing gate** on a `status: published` Insight is allowed for **backward compatibility**. Missing gate must **not** be interpreted or written as Editorial APPROVE / `gate_status: passed`.
6. **Do not** add or change `gate_status` / `hard_gate_status` on `smart-cabinet-five-process-metrics` or either scheduled P0 file.
7. **Daily behavior remains unchanged** and still requires an explicit passing hard gate.
8. Preview/review surfaces must not weaken production eligibility.
9. Search index / sitemap / feeds must continue to use the same production eligibility helper.

### 3.2 Data runtime-state invariants

1. Tests and fixtures **must not write** to `data/state/research_atoms.json`, `research_review_queue.json`, or other default durable paths.
2. Default durable paths remain for **real operators / CLI** only; every `persist=True` discovery test must explicitly set `pool_path`, `queue_path`, and `atoms_path` under `tmp_path`.
3. Contaminated runtime files (`research_atoms.json`, `research_review_queue.json`) are **quarantined by move/rename backup**, never raw-deleted. `seen_ids.json` is left untouched.
4. No test may assume production state contents; no CI job may commit `data/state/*`.
5. Claim verification / Editorial APPROVE / Channel APPROVE / publish remain human-gated.

### 3.3 Process invariants

1. Model: **Auto only**.
2. Execution: **inline / sequential**, **no subagents**. Workstream A → human acceptance → Workstream B.
3. No commit / push / merge / deploy / WeChat broadcast / Zhihu publish without explicit human approval.
4. Preserve all listed dirty/untracked files in both repos exactly as found.
5. Do not assume PR #15 is merged.

---

## 4. Chosen design

### 4.1 Website publication safety (Workstream A — P0, implement first)

**Two-layer defense:**

**Layer 1 — Content freeze (immediate, reversible, content-only):**  
For the two P0 MDX files, set `visibility: "private"` and keep `status: "scheduled"`. Do **not** set `status: published`. Do **not** add or change `gate_status` / `hard_gate_status` on either file.

**Layer 2 — Eligibility model fix (code + regression tests):**

1. Add `scheduled` to `NON_PUBLIC_STATUSES` so `status: scheduled` stays non-public even after its date.
2. Non-daily / Insight public eligibility:
   - `isPubliclyPublished` must pass (which now rejects `scheduled`);
   - explicit rejecting gates (`rejected` / `failed` / `blocked`) → ineligible;
   - require explicit `status === "published"`;
   - **missing gate on `status: published` Insight remains eligible** (backward compatibility);
   - do **not** require a passing gate for Insight;
   - do **not** treat missing gate as Editorial APPROVE.
3. Update / replace the outdated unit assertion that currently expects `scheduled` + today’s date → public.
4. Add frozen-clock tests at `2026-09-02T12:00:00+08:00` and `2026-09-03T12:00:00+08:00` proving both P0 files remain ineligible until frontmatter is explicitly human-approved (`status: published` + `visibility: public`, and no rejecting gate).
5. Keep Daily behavior unchanged (still requires explicit passing hard gate).
6. Assert already-public `smart-cabinet-five-process-metrics` remains eligible **without** adding a gate field.

**Explicit human publication path for Insight (after safety closure):**

1. Human changes frontmatter through a **reviewed content change**: `status: published` and `visibility: public`.
2. If any rejecting gate exists, resolve it **manually** (clear or pass) before publish — never auto-write APPROVE.
3. Human merge → human production deploy. No calendar auto-flip. No agent merge/deploy.

### 4.2 Data runtime-state integrity (Workstream B — only after A acceptance)

**CEO-approved quarantine (after A acceptance, reversible):**

1. Snapshot evidence: hashes, sizes, `updated_at` for `research_atoms.json` and `research_review_queue.json`.
2. Create timestamped ignored quarantine directory (e.g. `data/state/_quarantine/<timestamp>/`).
3. **Move** (not delete) the two active JSON files into that quarantine.
4. Verify destination contents; document restore instructions.
5. Leave `seen_ids.json` untouched.
6. Never delete.

**Test isolation safeguards (test-first quality bar):**

1. The **first new guard must FAIL** against the current leaking test constructors (callers that use `persist=True` without all three isolated paths).
2. That same guard must **PASS only after** all `persist=True` discovery tests explicitly set `pool_path`, `queue_path`, and `atoms_path` under `tmp_path`.
3. A **static AST-based test** over relevant discovery test files is an acceptable red/green guard.
4. A safe-pipeline test that already passes before fixing callers is **not** sufficient as the red test.
5. Fix all leaking `DiscoveryPipeline` / `DiscoveryPipelineConfig` constructions accordingly.
6. Do not change production CLI defaults for real operator runs in the same PR unless necessary; isolation is a test/fixture concern first.

### 4.3 Separation of concerns and sequencing

| Concern | Touches | Does not touch | When |
|---|---|---|---|
| Website publication safety | `zerorealm-website` eligibility + Insight frontmatter + tests | `zerorealm-data` state files, PR #15 code | Workstream A first |
| Data state integrity | `zerorealm-data` discovery tests/helpers + quarantine of the two contaminated JSON files | Website MDX, eligibility TS, PR #15 quality evaluator, `seen_ids.json` | Workstream B after A acceptance |

---

## 5. Alternatives rejected

| Alternative | Why rejected |
|---|---|
| **Rely on date gate only** (leave `scheduled` auto-public on date) | Exactly the P0 failure mode; no human approval |
| **Only flip MDX to private, no eligibility change** | Fragile; next scheduled Insight repeats the bug |
| **Require Insight hard-gate pass for public eligibility** | CEO: missing gate on published Insight allowed; do not add gates to existing content |
| **Add `gate_status: passed` to five-process-metrics or scheduled files** | Explicitly forbidden; missing gate ≠ Editorial APPROVE |
| **Delete contaminated state files** | Irreversible; violates quarantine policy |
| **Fold state isolation into PR #15** | Scope pollution; PR #15 is quality/shadow; CI already green; review risk |
| **Start Workstream B before A acceptance** | CEO: A website P0 first; B only after A acceptance |
| **Subagent-driven execution** | CEO: inline/sequential only |
| **Wait for PR #15 merge before any safety work** | Website P0 is independent and time-sensitive (Sep 2/3) |
| **Auto-clean state in pytest session fixtures writing empty production files** | Still touches production path; prefer never opening that path in tests |
| **Commit empty state templates into git** | Conflicts with `data/*` ignore policy and “runtime only” design |
| **Quarantine or modify `seen_ids.json`** | CEO: leave untouched |
| **Safe-pipeline-only regression as the red test** | Passes before callers are fixed; insufficient isolation quality bar |

---

## 6. Repo / branch / worktree strategy

### 6.1 Do not put data-state safeguards inside PR #15

PR #15 remains DeepSeek Content Quality v1 only. **Data-state isolation belongs on a follow-up branch**, not as a commit on `feature/deepseek-content-quality-v1`.

Recommended mapping:

| Workstream | Repo | Base branch | New branch (suggested) | Relation to PR #15 | Sequence |
|---|---|---|---|---|---|
| Website publication safety | `zerorealm-website` | `main` | `hotfix/insight-scheduled-publish-gate-20260808` | **Independent** | **First** |
| Data state isolation + quarantine | `zerorealm-data` | `master` (current origin tip; **do not require PR #15 merge**) | `hotfix/runtime-state-test-isolation-20260808` | **Follow-up**; not part of PR #15 | **Only after A acceptance** |

### 6.2 Execution guidance

- **Inline / sequential** in one Auto session. **No subagents.**
- Prefer isolated git worktrees for code changes so primary dirty checkouts stay untouched (create worktrees only when **executing** the implementation plan—not while editing these docs).
- Never check out / reset primary dirty trees in a way that drops known untracked assets.
- Planning docs may live on `zerorealm-data` even when describing website work (this file).

### 6.3 Merge order (human-gated)

1. Website hotfix → human review → human acceptance of Workstream A → human merge → human production deploy (before 2026-09-02 Shanghai).
2. **Only after A acceptance:** data isolation hotfix + CEO-approved quarantine → human review → human merge.
3. PR #15 remains its own merge decision.

---

## 7. Manual approval boundaries

| Action | Who | Automation allowed? |
|---|---|---|
| Edit eligibility / tests / MDX freeze | Implementer (Auto) after plan approval | Yes, in branch (Workstream A) |
| Commit / push | Human explicit ask | No by default |
| Merge PR | Human | No |
| Production deploy (Vercel/host) | Human | No |
| Editorial APPROVE / hard_gate pass in content | Human editor | No — missing gate must not be written as APPROVE |
| Insight publish frontmatter (`status`/`visibility`) | Human via reviewed content change | No auto flip |
| Channel APPROVE | Human | No |
| WeChat broadcast / freepublish | Human | No |
| Zhihu publishing | Human | No |
| Quarantine move of the two runtime JSON files | Implementer in Workstream B after A acceptance (CEO-approved) | Manual command; never delete |
| Touch `seen_ids.json` | Do not | No |
| Restore from quarantine | Human | Manual |

---

## 8. Rollback / quarantine approach

### 8.1 Website

- Revert hotfix PR or revert commit on `main`.
- Restore prior frontmatter from git history for the two MDX files if freeze must be undone.
- Eligibility rollback is safe only if MDX freeze remains or dates are still future.

### 8.2 Data state

```text
# Conceptual procedure (execution plan has exact commands)
# Snapshot hashes / size / updated_at first
mkdir data/state/_quarantine/<timestamp>/
move research_atoms.json      → _quarantine/<timestamp>/
move research_review_queue.json → _quarantine/<timestamp>/
# NEVER: rm research_atoms.json / research_review_queue.json
# NEVER: move or modify seen_ids.json
# Restore: move files back from quarantine
```

Quarantine directory must remain gitignored (under `data/` or `tmp_artifacts/`).

---

## 9. Acceptance criteria

### 9.1 Website (Workstream A)

- [ ] With clock fixed to 2026-09-02 and 2026-09-03 Shanghai, both P0 Insights fail `isPublicContentEligible` / `isProductionPublicEligible`.
- [ ] `getAllInsights()` and search index generation omit both slugs until human sets `status: published` + `visibility: public` (and no rejecting gate).
- [ ] `status: scheduled` never public regardless of date.
- [ ] Non-daily public eligibility requires explicit `status: published`; rejecting gates hide; **missing gate on published Insight remains eligible**.
- [ ] No `gate_status` / `hard_gate_status` added or changed on five-process-metrics or either scheduled file.
- [ ] Daily hard-gate rules unchanged and still green.
- [ ] Targeted + full relevant website test suites pass.
- [ ] Human acceptance recorded before Workstream B starts.

### 9.2 Data (Workstream B — after A acceptance)

- [ ] Contaminated `research_atoms.json` and `research_review_queue.json` quarantined via move/backup after snapshot; destination verified; restore instructions documented; never deleted.
- [ ] `seen_ids.json` untouched.
- [ ] First isolation guard **fails** against current leaking `persist=True` constructors (AST or equivalent); **passes** only after all such callers set `pool_path`, `queue_path`, and `atoms_path` under `tmp_path`.
- [ ] Relevant `pytest` suites pass; no secrets; no commit of `data/state`.

### 9.3 Process

- [ ] Executed inline/sequentially; no subagents.
- [ ] Workstream B started only after A acceptance.
- [ ] PR #15 scope preserved (unchanged by these hotfixes).
- [ ] No merge/deploy/publish performed by the agent without human approval.
- [ ] Known dirty/untracked files in both repos remain intact.

---

## 10. Out of scope (this safety closure)

- Growth experiment content calendar after safety closure
- Live WeChat/Zhihu publishing
- Merging PR #15
- Changing DeepSeek quality evaluator behavior
- Committing runtime state into git
- Adding Insight hard-gate pass requirements or writing `gate_status: passed` onto existing content
- Quarantining or modifying `seen_ids.json`
- Subagent-driven or parallel A+B execution

---

## 11. Implementation plan pointer

Executable task breakdown:  
`docs/plans/2026-08-08-publication-safety-and-state-integrity.md`
