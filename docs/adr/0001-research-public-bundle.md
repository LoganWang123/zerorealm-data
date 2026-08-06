# ADR 0001: Research domain models and Public Bundle

## Status

Accepted — 2026-08-06

## Context

`zerorealm-data` already has crawlers, AI runtime, processors, knowledge storage,
and a mature `PublishWorkflow` / WeChat publishing path. The bottleneck is not
another Research OS, but:

1. The daily `Article` model carrying too many long-lived knowledge duties.
2. No stable contract between research data and the website.
3. Two website sync paths (local `run_daily.py` git push vs GitHub Actions).

## Decision

1. Keep two repositories: `zerorealm-data` produces content; `zerorealm-website`
   only renders Public Content Bundle v1.
2. Add a `research/` package with domain models including `IndustrySignal`,
   `SourceDocument`, `Evidence`, `Claim`, company/case/metric profiles, and
   `ResearchBrief`. Do not replace `publishing.article.Article`.
3. Adapt research briefs to `Article` for WeChat; website consumes
   `dist/public-v1/` JSON schemas under `contracts/public-v1/`.
4. GitHub Actions remains the intended automatic cross-repo sync path. Local
   `run_daily.py` defaults to no website push; `--push-website` keeps an
   explicit escape hatch until Actions sync is fully stable.
5. Research evidence validation happens in a dedicated
   `ResearchPublishService` before Adapter → `PublishWorkflow.run_article()`,
   not by stuffing research objects into `PipelineContext`.
6. Git-reviewed structured research data is the source of truth; Supabase stays
   optional index/cache.

## Consequences

- Existing daily MDX and WeChat draft flows keep working unchanged.
- New exporters in phase one of migration: `public_bundle` and `zhihu` only.
- Website and WeChat channel exporters are not duplicated; WeChat continues to
  use the existing Article renderer/publisher.
- Baseline tag: `pre-research-v1`.
