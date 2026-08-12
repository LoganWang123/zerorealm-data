# DATA PR — ready to create

**Compare / create URL:** https://github.com/LoganWang123/zerorealm-data/compare/master...phase2-public-bundle?expand=1

**Title:** Research Platform v1: Public Bundle, MediaJob, Content Launch 01

**Base:** `master`  
**Head:** `phase2-public-bundle`

## Summary
- Research domain + Public Bundle v1 export/validation gates
- ResearchPublishService + channel adapters + Zhihu package export
- Agnes image generation disabled; IDE-assisted MediaJob workflow
- Content Launch 01: metric briefs, company review queue, draft cases/signals
- CI dual-write Bundle beside legacy MDX

## Test plan
- [ ] `ruff check .`
- [ ] `python -m pytest -q`
- [ ] Confirm CI has no `AGNES_API_KEY` media injection
- [ ] Spot-check `data/research/review-queue-companies.json` remains draft-only
- [ ] Public Bundle validation only exports approved metrics (draft companies/cases/signals stay out)

## Manual checklist
- [ ] No `.env` / secrets committed
- [ ] WeChat stash `wip: wechat publishing` untouched
- [ ] No auto-approve of draft companies/cases/signals
- [ ] No production WeChat mass send / Zhihu auto publish from this PR

## Out of scope
- No production WeChat mass send
- No auto-approve companies/cases/signals
- Do not commit `.env`, `output/`, unreviewed media as approved

Refs: `docs/reports/pr-data-research-platform-v1.md`

## Local verification (this session)
- `ruff check .` PASS
- `python -m pytest -q` → 365 passed
