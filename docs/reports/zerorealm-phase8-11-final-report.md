# ZeroRealm Phase 8–11 Final Report (Data Repo)

日期：2026-08-07

## 1. Phase 完成情况

| Phase | 状态 | Tag |
|------|------|-----|
| 8 Security + Agnes offline + local media | Done | `research-phase8-complete` |
| 9 Content review efficiency | Done | `research-phase9-complete` |
| 10 Industry map + relations | Done | `research-phase10-complete` |
| 11 SEO helpers on website + content package + release | Done | `research-phase11-complete` / `zerorealm-release-candidate-v1` |

网站仓对应工作见 `zerorealm-website/docs/zerorealm-phase8-11-final-report.md`。

## 2. Agnes 生图下线

- 生产工厂不再构造 `AgnesClient`
- `provider=agnes` → `AgnesImageGenerationDisabled`
- CI 移除 `AGNES_API_KEY` 注入
- 详见 `docs/reports/agnes-image-generation-deprecation.md`

## 3. Active Image Provider

`local` → `LocalImageGenerator`（可选 `ZEROREALM_LOCAL_IMAGE_CMD`，否则程序化模板）

## 4. 本地生图能力

- Cursor/本机未配置专用扩散模型命令时：使用 Pillow 程序化模板，或 `--prompt-only` 写 job
- 状态码：`LOCAL_IMAGE_GENERATOR_UNAVAILABLE` / `pending_local_generation`

## 5. Agnes production invocation count

策略测试断言为 **0**（`tests/test_local_media_policy.py`）

## 6. 图片调用链

Research/Daily → ImageBrief → Local generation → asset_checks → review_media (SHA) → WeChat upload / content package

## 7. Prompt fallback

local unavailable → `dist/media-jobs/<slug>/`（brief + prompts + metadata），不调用 Agnes

## 8–11. 文件 / Commit / Tags / Tests

以 `git log` / `git tag` 为准；本报告提交后更新 HEAD。

## 12. Security

`docs/reports/security-secret-review.md` — 无自动确认的历史真密钥；文档项需人工复核；本地 `.env` 建议轮换。

## 13. Company review queue

`data/research/review-queue-companies.json` + `docs/reports/company-review-priority.md`

## 14. 数据统计（catalog）

- companies: 52 draft
- metrics: 15 approved
- signals/cases approved: 0

## 15–18. Industry Map / SEO / Search / Content Package

- Map audit + migrate dry-run + dataset export（data）
- SEO/Search/OG（website）
- `scripts/export_content_package.py`

## 19. Media Policy

`docs/architecture/media-generation-policy.md` 与 release 包副本

## 20. Known limitations

见 `release/zerorealm-research-platform-v1/known-limitations.md`

## 21. Blockers

无代码阻塞。人工项：企业事实审核、密钥轮换确认、push/merge。

## 22. Manual actions

见 release `manual-checklist.md`
