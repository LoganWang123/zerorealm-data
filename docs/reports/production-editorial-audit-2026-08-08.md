# Production Editorial Audit — 2026-08-08

**Scope:** the 7 Daily digests published/staged between 2026-07-28 and 2026-08-08
(`zerorealm-website/content/daily/2026-07-28.mdx` … `2026-08-08.mdx`), reviewed
against the single-signal-daily editorial policy, and the production
homepage/prev-next navigation inconsistency reported for 2026-08-08.

**Hotfix branch:** `hotfix/production-editorial-gate-20260808`
**New hard gate:** `publishing/editorial_gate.py` (`run_daily_editorial_gate`),
wired into `publishing.workflow.PublishWorkflow.build_steps()` as
`EditorialGateStep`, running **before** `RenderStep`/`PublishStep` for both
the Website and WeChat channels (they share the same step sequence).

---

## 1. Executive summary

Production currently serves a stale build in which the 2026-08-08 Daily slot
still resolves to the withdrawn **Dongpeng (东鹏饮料)** single-company-growth
draft on homepage/prev-next navigation, even though the repository's
`content/daily/2026-08-08.mdx` has already been replaced with the corrected
**Insight-pointer** Daily (single core signal, points to
`/insight/smart-cabinet-five-process-metrics`, `gate_status: passed`). This is
a **deployment/staleness issue, not a content issue** — see [§4](#4-root-cause-homepagepre-next-inconsistency-on-2026-08-08)
for the two compounding root causes.

Per-daily disposition (human/editorial review, summarized below) plus what
the newly implemented heuristic hard gate (`run_daily_editorial_gate`) would
flag if run against equivalent content today:

| Date | Disposition | Primary issues |
|------|-------------|-----------------|
| 2026-07-28 | **FAIL** | `MULTI_SIGNAL_DAILY` (2 core signals), `PSEUDO_PRECISION`/`UNSOURCED_PREDICTION` (per-item `confidence_pct` with no disclosed methodology), pseudo-quantified `trend` (stars+streak) |
| 2026-07-29 | **PASS_WITH_EDIT** | `OVERGENERALIZED_HEADLINE` ("59,000台柜实验**证明**…") — single RCT generalized as proof; headline required editing before it could ship |
| 2026-07-30 | **PASS_WITH_EDIT** | Dongpeng-style single-company earnings (营收 +15.89%, 净利润 +20.72%) used as the news hook for an operator decision keyed to SKU-level 动销率/缺货率 — a `METRIC_DIMENSION_MISMATCH`/`SINGLE_COMPANY_MARKET_GENERALIZATION` pattern; shipped only because the body explicitly hedges ("这组数字…不能直接证明…不能替代柜机自己的交易数据") and the decision block stays scoped to a 10-cabinet sample |
| 2026-07-31 | **PASS_WITH_EDIT** | Same single-company → operator-decision pattern (中吉 0-算力费), hedged and sample-scoped; unlabeled "10台/3个月" parameters needed a "建议起点" framing pass before shipping |
| 2026-08-01 | **PASS** | Single-signal-daily, one disclosed government source, no predictions, no thresholds — the reference-clean pattern (see [§5](#5-recommendations)) |
| 2026-08-06 | **FAIL** (`gate_status: rejected`, `visibility: private` in repo) | `MULTI_SIGNAL_DAILY` (2 core signals), pseudo-quantified `trend` (stars 1–5 + streak days) with no disclosed methodology, `ceo_radar.prediction_validation` percentages without sourcing |
| 2026-08-08 | Repo: **PASS** (Insight-pointer, single signal, `gate_status: passed`) — **Production still resolves the withdrawn Dongpeng draft on nav/homepage** | Not a content defect in the repo; see [§4](#4-root-cause-homepagepre-next-inconsistency-on-2026-08-08) |

This audit report captures the findings and encodes the underlying rules into
`publishing/editorial_gate.py` so the next incident is caught mechanically,
pre-render/pre-publish, instead of relying solely on manual review.

---

## 2. Per-daily findings

### 2026-07-28 — FAIL

- **`MULTI_SIGNAL_DAILY`**: two `level: core` sections ("新华书店入驻闪购" and
  "Gap重启90年代香水") in one Daily. The single-signal-daily policy allows
  exactly one core signal per issue; readers cannot act on two unrelated
  "must read today" stories with equal weight.
- **`UNSOURCED_PREDICTION` / `PSEUDO_PRECISION`**: both core items carry a
  per-item `prediction.confidence_pct` (70%, 60%) backed only by a bulleted
  "evidence" list restating the news itself (no sampling, backtest, or
  survey methodology disclosed) — a textbook false-precision pattern.
  `decision.*.confidence_pct` (75/80/70/65%) repeats the same pattern at the
  role level.
- **`PSEUDO_PRECISION`** (secondary): `trend` items carry `stars` (1–5) +
  `streak` (days) with no disclosed scoring methodology.

### 2026-07-29 — PASS_WITH_EDIT

- **`OVERGENERALIZED_HEADLINE`**: draft headline used "…证明：人工改补货单要设上限"
  to describe one 46-day, single-operator randomized trial (553 replenishers,
  ~59,000 machines). A single RCT — however well-designed — does not
  "prove" a universal operating rule; it supports a **directional,
  sample-scoped recommendation**. Edited before publish so the verdict frames
  the 2-SKU cap as a hypothesis to test locally, not a proven law.
- Everything else in this issue is a model example: methodology is disclosed
  in-line ("46天随机实验", "553名补货员", "59,000多台机器"), the follow-up test
  design specifies its own N (20 cabinets / 10 vs 10) and an explicit
  stop-condition, and the source is a real paper (`arXiv`).

### 2026-07-30 — PASS_WITH_EDIT (Dongpeng pattern)

- Single-company financial disclosure (东鹏饮料 营收 +15.89% / 净利润 +20.72%)
  used as the news hook, immediately re-scoped to an operator decision about
  **SKU-level** 缺货率/毛利贡献 — a company-level metric feeding a
  per-SKU-dimension decision (`METRIC_DIMENSION_MISMATCH` pattern) and a
  single company standing in for "饮料旺季" broadly (`SINGLE_COMPANY_MARKET_GENERALIZATION`
  pattern).
- Shipped as **PASS_WITH_EDIT** rather than FAIL specifically because the
  body carries an explicit hedge — *"这组数字能确认的是饮料消费和头部品牌经营仍有增长，
  但它不能直接证明某个点位…一定适合你的柜机"* — and the recommended action is
  capped to a 10-cabinet sample over 7 days with an explicit stop-condition.
  This is exactly the boundary the new gate's `HEDGE_MARKERS` check is
  designed to respect: the same claim *without* that disclaimer sentence is
  precisely what `tests/test_editorial_gate.py::test_dongpeng_style_channel_inference_fails`
  encodes as a hard failure.

### 2026-07-31 — PASS_WITH_EDIT

- Same shape as 07-30 (single vendor announcement — 中吉 0-算力费 AI 柜 — driving
  an operator cost decision). Required an editing pass to add the
  "先拉出过去3个月每台AI柜的实际账单" framing and cap the sample (10 cabinets) before
  the "10台/3个月" parameters read as a suggested starting point rather than a
  universal rule.

### 2026-08-01 — PASS (reference-clean)

- Single core signal, single disclosed government source
  (`sw.beijing.gov.cn`), an explicit `scope_guard` field limiting applicability
  ("仅适用于运营商自行使用电动自行车补货，或依赖…即时配送运力的场景；不适用于所有智能柜补货"),
  no predictions, no unlabeled thresholds. This is the fixture used for
  `test_single_signal_daily_with_sources_passes` in `tests/test_editorial_gate.py`.

### 2026-08-06 — FAIL (already `gate_status: rejected` / `visibility: private` in repo)

- **`MULTI_SIGNAL_DAILY`**: two `level: core` sections (即时零售基建共享 /
  AI Agent, and 智能柜成本+补货合规).
- Pseudo-quantified `trend` (5 topics with `stars` 4–5 and `streak` up to 10
  days) with no disclosed derivation.
- `ceo_radar.prediction_validation` entries embed bare percentages
  ("京东跟进图书小时达（70%）") with no sourcing.
- Already correctly excluded from public surfaces in the repo
  (`gate_status: rejected`, `visibility: private`); `isPublicContentEligible()`
  in `zerorealm-website/lib/publish-eligibility.ts` filters it out of
  `getAllDailies()`/`getDailyByDate()`.

### 2026-08-08 — Repo: PASS. Production: stale Dongpeng claims still resolving.

- Current repo content (`content/daily/2026-08-08.mdx`): single core signal,
  points to the same-day WeChat Insight
  (`/insight/smart-cabinet-five-process-metrics`), `gate_status: passed`,
  `reviewed_at` set, `source_url` disclosed. This passes the hard gate
  cleanly (see `tests/test_editorial_gate.py`, single-signal fixtures).
- Per `docs/reports/hotfix-insight-wechat-homepage-align-20260808.md`, the
  original 2026-08-08 Daily draft ("东鹏饮料净利增两成…") was **withdrawn** and
  replaced with the Insight-pointer Daily; no WeChat re-publish occurred (and
  this audit/hotfix likewise does not touch any WeChat draft/package).
- **Production is still showing the withdrawn Dongpeng framing on
  homepage/prev-next navigation** as of this audit. Root cause below.

---

## 3. P0 / P1 issue list

| Priority | Issue | Where | Status after this hotfix |
|----------|-------|-------|---------------------------|
| **P0** | Production homepage + Daily prev/next nav resolve 2026-08-08 to the withdrawn Dongpeng draft instead of the repo's current Insight-pointer Daily | Production deployment (stale build), not the repo | Requires a fresh deploy/rebuild — see [§4](#4-root-cause-homepagepre-next-inconsistency-on-2026-08-08) and [§5](#5-recommendations) |
| **P0** | No mechanical gate existed before this hotfix: `MULTI_SIGNAL_DAILY`, `UNSOURCED_PREDICTION`/`PSEUDO_PRECISION`, and `UNSUPPORTED_CHANNEL_INFERENCE` daily patterns (07-28, 08-06) could reach `RenderStep`/`PublishStep` and were only caught by manual review after the fact | `publishing/workflow.py` pipeline | **Fixed**: `EditorialGateStep` now runs immediately after `ValidateStep`, before `GenerateMediaStep`/`RenderStep`/`PublishStep`, for both Website and WeChat channels |
| **P0** | A `manual_reviewed`/legacy `gate_status: passed` flag with no `editorial_exception` could, in principle, be used to argue a hard failure was "reviewed and fine" | Editorial process | **Fixed**: `is_bypass_allowed()` ignores `manual_reviewed`/legacy flags entirely; only a structured `editorial_exception` with `reason` + `approved_at` can waive a *bypassable* failure, and never `UNSUPPORTED_FACT` / `SOURCE_LINEAGE_INCOMPLETE` / `FABRICATED_DATA` / `FUTURE_PUBLICATION` |
| **P1** | Website eligibility previously allowed Daily content with a **missing** `gate_status` to be treated as eligible ("legacy" bypass) | `zerorealm-website/lib/publish-eligibility.ts` | Already fixed in the repo (`isPublicContentEligible` now requires an explicit passing `gate_status` for `type: daily`; see code comment "there is no legacy bypass for Daily content") — this audit confirms the fix and adds the data-side gate as defense in depth |
| **P1** | Single-company financial disclosures (07-30, 07-31 pattern) can slide into channel-wide claims without an explicit hedge sentence | Daily content prompts/authoring | Partially mitigated by editorial hedge-sentence convention (already present in 07-30/07-31); now mechanically enforced by `UNSUPPORTED_CHANNEL_INFERENCE` / `SINGLE_COMPANY_MARKET_GENERALIZATION` / `METRIC_DIMENSION_MISMATCH` checks |
| **P1** | Experiment-style parameters ("N台", "N天", "毛利低于N%") read as universal operating rules unless explicitly labeled as a starting point | Daily content authoring | Now mechanically enforced by `UNLABELED_EXPERIMENT_PARAMETER` / `UNSUPPORTED_THRESHOLD` checks (require a "建议起点/示例试验/企业自定义" label) |

---

## 4. Root cause: homepage/prev-next inconsistency on 2026-08-08

Two compounding causes, confirmed by reading `zerorealm-website/lib/mdx.ts`
and `zerorealm-website/lib/publish-eligibility.ts`:

1. **Stale static nav / stale deployment.** `zerorealm-website` is a
   statically-rendered Next.js site: the homepage's "latest Daily" module and
   the Daily detail page's prev/next links (`app/daily/[date]/page.tsx`) are
   both derived from `getAllDailies()`, a build-time snapshot of
   `content/daily/*.mdx` sorted by date. The 2026-08-08 content swap
   (Dongpeng draft → Insight-pointer Daily, per
   `docs/reports/hotfix-insight-wechat-homepage-align-20260808.md`) was
   committed to the repository, but production has not been rebuilt/redeployed
   since. Until the next deploy, production continues to serve the HTML/JSON
   generated from the **old** `2026-08-08.mdx` content, so both the homepage
   card and the prev/next nav on adjacent Daily pages still show the Dongpeng
   framing.
2. **Eligibility previously allowed a missing `gate_status` for Daily
   content ("legacy" bypass).** Independent of the staleness issue,
   `isPublicContentEligible()` in `lib/publish-eligibility.ts` used to treat a
   **missing** `gate_status` on `type: daily` content as implicitly eligible
   (the same "missing status ≈ published" leniency that is intentionally kept
   for non-Daily content, e.g. Insight, per the function's docstring). That
   meant any pre-gate legacy Daily draft — including an earlier version of
   the 2026-08-08 Dongpeng draft that predates the `gate_status` field being
   populated — could have been served publicly even without ever passing a
   hard gate. **This has since been corrected in the repo**: for
   `type === "daily"`, `isPublicContentEligible()` now requires an explicit
   passing disposition (`passed` / `pass` / `passed_with_edit`) —
   `DAILY_PASS_GATE_STATUSES` — with **no legacy bypass**, confirmed by
   `zerorealm-website/tests/publish-eligibility.test.ts::"rejected gate daily
   is not publicly eligible"` and
   `"eligible public dailies surface 2026-08-08 five-process-metrics Insight
   post"`. The eligibility fix alone does not resolve the production
   inconsistency because of cause (1) above — a stale build still serves the
   pre-fix HTML regardless of what the eligibility function does today.

Net effect: cause (2) is why an ungated Dongpeng draft could have reached
production in the first place; cause (1) is why it is still visible on
navigation surfaces today even though the repository has moved on. Neither
cause originates in the `zerorealm-data` publishing pipeline that this hotfix
modifies — this hard gate closes the analogous gap on the **data/publish
side** (no daily payload reaches `RenderStep`/`PublishStep` without a
disposition), so future incidents fail before reaching the website content
directory at all.

---

## 5. Recommendations

1. **Redeploy `zerorealm-website` from the current `main`** so the
   homepage/prev-next nav rebuild against the corrected
   `content/daily/2026-08-08.mdx`. This is an ops/deploy action outside
   `zerorealm-data`; no content or WeChat changes are required on this side.
2. **Keep `EditorialGateStep` first in the shared pipeline** (right after
   `ValidateStep`, before any media generation/rendering/publishing) for both
   channels — already done in this hotfix
   (`publishing/workflow.py::PublishWorkflow.build_steps()`).
3. **Treat 2026-08-01 as the house style for single-signal dailies**: one
   core signal, one disclosed primary source, an explicit `scope_guard` when
   the finding only applies to a subset of operators, no predictions unless
   methodology is disclosed.
4. **Require an explicit hedge sentence whenever a single company's
   financials motivate an operator decision** (the 07-30/07-31 pattern) —
   already editorial convention; now backed by `UNSUPPORTED_CHANNEL_INFERENCE`,
   `SINGLE_COMPANY_MARKET_GENERALIZATION`, and `METRIC_DIMENSION_MISMATCH`.
5. **Label every experiment-style numeric parameter** ("N台", "N天",
   "毛利低于N%") as a "建议起点/示例试验/企业自定义" starting point, not a
   universal rule — enforced by `UNLABELED_EXPERIMENT_PARAMETER` /
   `UNSUPPORTED_THRESHOLD`.
6. **`editorial_exception` is the only bypass; manual review alone is not.**
   Any future exception request must carry a structured
   `editorial_exception: {reason, approved_at}` in the daily payload, and
   even then can never waive `UNSUPPORTED_FACT`, `SOURCE_LINEAGE_INCOMPLETE`,
   `FABRICATED_DATA`, or `FUTURE_PUBLICATION`.
7. **This gate is heuristic, not semantic.** It catches known-bad textual and
   structural patterns; it does not fact-check claims. Human editorial review
   remains required for anything outside these patterns — treat gate passes
   as "no known red flag," not "verified true."
8. **No WeChat republish / no modification of already-published WeChat
   packages** was performed or is recommended as part of this hotfix; the
   2026-08-08 WeChat Insight article is unaffected.

---

## 6. What shipped in this hotfix

- `publishing/editorial_gate.py` — `EditorialGateErrorCode`, `GateIssue`,
  `EditorialGateResult`, `run_daily_editorial_gate()`, `is_bypass_allowed()`.
- `publishing/article.py` — `Article.raw` (full-fidelity source frontmatter,
  populated by `ArticleParser`, defaults to `{}` for hand-built `Article`s).
- `publishing/parser.py` — populates `Article.raw` from the parsed frontmatter.
- `publishing/pipeline.py` — `PipelineState.EDITORIAL_GATE_RESULT`.
- `publishing/steps.py` — `EditorialGateStep` (runs the hard gate on
  Daily-sourced articles that carry `raw` frontmatter; skips non-daily
  sources and hand-built articles with no `raw` payload).
- `publishing/workflow.py` — `EditorialGateStep` inserted into
  `PublishWorkflow.build_steps()` right after `ValidateStep`, ahead of media
  generation, rendering, and both channel publishers.
- `tests/test_editorial_gate.py` — 17 tests covering every required scenario
  (Dongpeng-style channel inference, claim/evidence contradiction, unlabeled
  thresholds, single-signal-with-sources pass, multi-signal+predictions fail,
  manual-review-alone-does-not-bypass) plus bypass/non-bypass and pipeline
  wiring coverage.
- `docs/reports/production-editorial-audit-2026-08-08.md` — this report.

No WeChat draft/package was touched; no already-published WeChat content was
modified or resubmitted.
