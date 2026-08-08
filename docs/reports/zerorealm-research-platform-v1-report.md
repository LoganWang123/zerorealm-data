# ZeroRealm Research Platform v1 总报告

## 1. 执行摘要

已完成 Phase 2–7（在既有 Phase 0/1 之上）的本地实现：

- Public Bundle v1 契约、序列化、原子导出、CLI
- ResearchPublishService + Article Adapter + `run_article` + 知乎发布包
- Actions 双写日报 MDX 与 Public Bundle
- 中文官网 Bundle Reader 与企业/案例/指标/信号路由
- 首批 15 个已审核指标定义；52 家企业档案保持 draft
- 架构/内容治理/运行文档

**阻塞提醒（安全）：** 本机 `zerorealm-data/.env` 存在疑似真实 API 密钥。该文件当前被 `.gitignore` 忽略、未纳入 Git 跟踪，但仍需你立即在各服务商轮换密钥，并确认从未提交到远端历史。本报告不复制任何密钥值。

未 push 任何远端。

## 2. Commit 清单（数据仓 `phase2-public-bundle`）

| Hash | Message |
|------|---------|
| 4859548..45a91f5 | Phase 0/1（已在 master） |
| b125a15 / afdbf28 / 5f9c9a1 / c6a3e2b | Phase 2 Public Bundle |
| 85712e5 / 2d1bf67 | Phase 3 research publishing |
| 805c133 | Phase 4 Actions sync |
| 1c5d825 | Phase 6 bootstrap assets |
| e759721 | Phase 7 docs |

（以 `git log` 为准；本机另有对齐与 hardening 提交。）

### 网站仓 `phase5-public-bundle`

| Hash | Message |
|------|---------|
| 94404c6 | feat(web): consume Public Bundle v1 |
| 36102d2 | docs(web): delivery report |

## 3. 文件清单（关键）

### 数据仓新增

- `contracts/public-v1/*`
- `research/`（models, serialization, validators, intake, publishing_service, exporters）
- `publishing/adapters/*`
- `scripts/export_public_bundle.py` 及 bootstrap/migrate/audit 脚本
- `docs/adr` / `docs/architecture` / `docs/content-guidelines` / `docs/operations` / `docs/reports`

### 未重写

- `publishing/pipeline.py` 核心状态机
- WeChat Publisher 上传逻辑（仅增加研究模板渲染分支）
- crawlers / ai_runtime 生产链路

## 4. Public Bundle

- 目录：`dist/public-v1/`（manifest、content-index、signals、companies/cases/metrics/topics/claims/sources）
- contractVersion：`1.0`
- bundleHash：`sha256:<hex>`，基于业务文件路径与内容 hash
- 仅导出 approved/published/verified
- CLI：`python scripts/export_public_bundle.py --input ... --output ...`

## 5. 发布体系

- `ResearchPublishService` → Adapter → `PublishWorkflow.run_article()`
- 微信模板：`signal_digest` / `deep_insight` / `case_study` / `company_profile`
- 知乎：`dist/channels/zhihu/<slug>/`，不自动发布

## 6. 自动化

- Actions：导出 Bundle + 可选同步 `website/data/public-v1` + 保留 legacy MDX
- 本地 `run_daily` 默认不 push；`--push-website` 显式启用
- 无变化不提交

## 7. 网站

- Next.js 16 + React 19，中文默认
- `lib/public-bundle` + `/signals|/companies|/cases|/metrics`
- 旧 `/daily` 兼容保留
- 构建与测试已通过

## 8. 内容资产

| 类型 | 数量 | 状态 |
|------|------|------|
| 企业 | 52 | draft（不进 Bundle） |
| 指标 | 15 | approved（已进 Bundle） |
| 案例 | 0 | 无公开证据，不强行凑数 |
| 信号 | 0 | 待人工审核公开新闻 |
| 专题 | 1 | draft |

## 9. 测试

- 数据仓：`ruff check .` 通过；`python -m pytest -q` → **350 passed**
- 网站仓：`npm test` 33 passed；lint / tsc / build 通过

## 10. 安全

- Public Bundle 敏感字段隔离测试通过
- Actions 不打印 Token 值
- **发现：** 本地 `.env` 含疑似真实密钥（未跟踪）；请立即轮换
- 微信无关改动仍在 `git stash`：`wip: wechat publishing`

## 11. 已知限制

- 企业/案例/信号公开页仍为空态
- industry-map 硬编码未完全替换
- 未 push、未合并 master/main
- 未做真实微信/知乎外发
- 未引入搜索后端；网站为静态索引 + 页面筛选

## 12. 回滚

```bash
# 数据仓
git checkout pre-research-v1
git checkout research-phase1-complete
git checkout research-phase2-complete
# ... phase3-7 tags

# 网站仓
git checkout zerorealm-website-public-bundle-v1
```

## 13. 下一步建议（不实施）

- 人工审核企业档案并补公开来源后批准
- 免费资料领取转化漏斗
- 公众号关注转化优化
- Pro 会员 / 付费数字产品（更后期）
