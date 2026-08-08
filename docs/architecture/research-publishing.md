# Research Publishing Architecture

## Domain

`research/` holds long-lived assets: SourceDocument, Evidence, Claim,
IndustrySignal, CompanyProfile, CaseStudy, MetricDefinition, Topic, ResearchBrief.

## Public Bundle

`contracts/public-v1` + `research/serialization.py` + `research/exporters/public_bundle.py`
produce `dist/public-v1` for the website. Git-reviewed catalog JSON is the source of truth.

## Publishing

`ResearchPublishService` validates claims, adapts to `Article`, then calls
`PublishWorkflow.run_article()`. WeChat reuses existing renderer/publisher.
Zhihu exports a manual package only.

## Sync

GitHub Actions dual-writes legacy daily MDX and Public Bundle to the website
repository. Local `run_daily.py` defaults to no push.
