# PR Draft — zerorealm-data Research Platform v1

## Branch

`phase2-public-bundle` → suggest base `master`

## Summary

- Research domain + Public Bundle v1
- ResearchPublishService + adapters + Zhihu package
- Agnes image generation disabled; MediaJob + IDE-native workflow
- Content Launch 01: metric briefs, company review queue, draft cases/signals
- CI dual-write Bundle + legacy MDX

## Test plan

- [ ] `ruff check .`
- [ ] `python -m pytest -q`
- [ ] Confirm CI has no `AGNES_API_KEY` media injection
- [ ] Spot-check `data/research/review-queue-companies.json` remains draft-only

## Out of scope

- No production WeChat mass send
- No auto-approve companies/cases/signals
- Do not commit `.env`, `output/`, unreviewed media as approved
