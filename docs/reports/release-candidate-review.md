# Release Candidate Review — ZeroRealm Research Platform v1

- **日期：** 2026-08-07
- **模式：** RC 验收（不新增产品功能）
- **数据仓：** `zerorealm-data` @ `9176ced`（`phase2-public-bundle`，相对 `origin/phase2-public-bundle` ahead 7）
- **网站仓：** `zerorealm-website` @ `36102d2`（`phase5-public-bundle`，相对 `main` +2 commits）
- **结论：PASS**
- **阻塞项：无**

---

## 1. 最终 Diff 与架构审计

### 1.1 zerorealm-data（相对 `origin/phase2-public-bundle`）

关键路径（31 files, +3005 / −166）：

| 区域 | 关键 |
|------|------|
| Contract | `contracts/public-v1/*` 对齐 Bundle 布局 |
| Export | `research/exporters/public_bundle.py`、`scripts/export_public_bundle.py` |
| Publish bridge | `research/publishing_service.py`、`publishing/adapters/*`、`workflow.run_article` |
| Zhihu | `research/exporters/zhihu.py`（导出包，非直发） |
| CI | `.github/workflows/daily-crawl.yaml` dual-write Bundle + legacy MDX |
| Content | `data/research/public-catalog.json`（draft companies + approved metrics） |
| Docs | architecture / runbook / platform report |

**架构结论：**

- Research 域对象停留在 `research/` + adapters。
- `PublishPipeline` / `PublishWorkflow` / `publish.py` / WeChat publisher **不 import research**（AST 审计通过）。
- 微信 research 模板仅消费已适配的 `Article` 字段（`source`/`template`），不依赖 Research 类型。

### 1.2 zerorealm-website（相对 `main`）

关键路径（35 files, +1186 / −7）：

| 区域 | 变更 |
|------|------|
| Loader | `lib/public-bundle/{load,types,index}.ts` |
| Routes | `/signals` `/companies` `/cases` `/metrics`（列表+详情） |
| Data | `data/public-v1`（当前 15 metrics；signals/companies/cases 空态） |
| Nav/Sitemap | Header + sitemap 接入 Bundle 索引 |
| Tests | `tests/public-bundle.test.ts` |

**架构结论：**

- 日报页继续走 `lib/mdx` → `content/daily/*.mdx`，与 Bundle loader 分离。
- Bundle 页面只读 `data/public-v1`，无 research Python/领域依赖。

---

## 2. Public Bundle 核心对象脱敏样例

> 字段集来自 `research/serialization.py` 白名单。样例基于真实 Metric/Company 结构脱敏合成；不含 raw_excerpt / review_note / status 等内部字段。

### PublicSource

```json
{
  "id": "src-example-1",
  "title": "公开新闻标题（样例）",
  "url": "https://example.com/public-news/demo",
  "publisher": "公开媒体A",
  "publishedAt": "2026-08-01",
  "accessedAt": "2026-08-06T10:00:00+08:00",
  "sourceType": "web",
  "credibility": "high"
}
```

### PublicClaim

```json
{
  "id": "cl-example-1",
  "text": "某运营商宣布扩大办公楼场景投放（样例表述）",
  "type": "fact",
  "confidence": "high",
  "sourceIds": ["src-example-1"],
  "basedOnClaimIds": []
}
```

### IndustrySignal

```json
{
  "id": "sig-example-1",
  "slug": "demo-signal-2026-08-01",
  "title": "办公楼智能柜投放扩大（样例）",
  "summary": "公开报道称投放范围扩大",
  "whyItMatters": "影响补货半径与点位模型",
  "affectedRoles": ["operators"],
  "judgment": "值得跟踪公开披露的点位变化",
  "claimIds": ["cl-example-1"],
  "sourceIds": ["src-example-1"],
  "companyIds": [],
  "verificationStatus": "verified",
  "publishedAt": "2026-08-01",
  "tags": ["smart_cabinet"]
}
```

### CompanyProfile（结构取自 catalog，摘要已脱敏）

```json
{
  "id": "co-acde93c6cc3f",
  "slug": "co-acde93c6cc",
  "name": "丰e足食",
  "summary": "公开图谱收录的智能零售相关企业（脱敏摘要）",
  "coreBusiness": "operator",
  "products": [],
  "scenarios": ["办公楼"],
  "businessModel": "",
  "relatedCaseIds": [],
  "relatedSignalIds": [],
  "verifiedAt": ""
}
```

### CaseStudy

```json
{
  "id": "case-example-1",
  "slug": "demo-office-replenish",
  "title": "办公楼补货时效优化（样例）",
  "problem": "缺货率偏高",
  "solution": "按动销补货",
  "howItWorks": "日更动销驱动补货单",
  "publicResults": ["公开材料未给出可核验量化结果"],
  "limitations": ["不能照搬到冷启动点位"],
  "companyIds": []
}
```

### MetricDefinition（真实 approved：`stockout-rate`）

```json
{
  "id": "metric-stockout-rate",
  "slug": "stockout-rate",
  "name": "缺货率",
  "definition": "应售 SKU/货道中处于缺货状态的比例。",
  "formula": "stockout_slots / expected_slots",
  "applicableScenarios": ["即时零售履约", "智能柜补货"],
  "commonPitfalls": [
    "临时下架与真实缺货需区分",
    "不同企业口径可能不同，不能当作统一行业标准"
  ],
  "relatedCaseIds": []
}
```

### Topic

```json
{
  "id": "topic-example-1",
  "slug": "demo-replenishment",
  "title": "补货效率（样例）",
  "summary": "围绕缺货与补货时效",
  "signalIds": [],
  "companyIds": [],
  "caseIds": [],
  "metricIds": ["metric-stockout-rate"]
}
```

---

## 3. 调用链 A：ResearchBrief → PublishWorkflow.run_article

```
ResearchPublishService.publish(request, target, context, mode)
  ├─ validate(request)
  │    ├─ brief.status ∈ {approved, published}
  │    ├─ template ∈ ALLOWED_TEMPLATES
  │    ├─ claim 存在性 / ClaimStatus.VERIFIED
  │    └─ research.validators.validate_claims(claims, sources)
  ├─ research_brief_to_article(...)          # publishing/adapters/*
  │    └─ 产出 publishing.models.Article
  └─ PublishWorkflow.run_article(article, ...)
       ├─ build_steps()
       ├─ PublishPipeline(steps).run(PipelineContext)
       └─ 返回 PipelineState.PUBLISH_RESULT
```

**隔离确认（无 research import）：**

- `publish.py`
- `publishing/pipeline.py`
- `publishing/workflow.py`
- `publishing/steps.py`
- `publishing/validator.py`
- `publishing/wechat/publisher.py`
- `publishing/wechat/renderer.py`

Research 仅出现在：`research/publishing_service.py` 与 `publishing/adapters/*`。

---

## 4. 调用链 B：Public Bundle → Website 页面

```
data/public-v1/
  manifest.json / content-index.json / signals.json / {entities}/*.json
        ↓
lib/public-bundle/load.ts
  getManifest() / verifyBundleHashes() / getContentIndex()
  listSignals|Companies|Cases|Metrics|Topics / get*(slug)
        ↓
lib/public-bundle/index.ts  (re-export)
        ↓
app/{signals,companies,cases,metrics}/page.tsx
app/{signals,companies,cases,metrics}/[slug]/page.tsx
app/sitemap.ts  (getContentIndex)
```

当前静态生成：metrics 15 条详情页；signals/companies/cases 列表可空。

---

## 5. Bundle 异常场景验证

| 场景 | 结果 | 观测错误/行为 |
|------|------|----------------|
| 未知 `contractVersion` | PASS | `不支持的 Public Bundle 版本: 9.9` |
| Bundle 缺失 | PASS | `Public Bundle 缺少文件: manifest.json` |
| hash 错误 | PASS | `Public Bundle hash 不匹配: signals.json` |
| 空 Bundle | PASS | export 空 catalog 成功；loader 接受 counts=0 且 file hash 校验通过 |

数据侧空 Bundle：`export_public_bundle(ResearchCatalog())` → `counts.metrics == 0`，`bundleHash` 正常生成。

---

## 6. 旧日报 MDX → 微信链路独立性

```
content/daily/*.mdx（网站）  ← CI legacy sync / 人工
publish.py
  → PublishWorkflow.run(article_path)
      → parser.parse(path) → Article
      → run_article → PublishPipeline → WeChat renderer/publisher
```

- `publish.py` 无 `research` 引用。
- 网站日报：`app/daily/[date]/page.tsx` → `lib/mdx.getDailyByDate`（gray-matter），不经过 `lib/public-bundle`。
- Research 发布是可选旁路：`ResearchPublishService` → adapter → **同一** `run_article`；不改写旧 path 入口。

---

## 7. Git 历史敏感信息扫描

扫描范围：两仓当前 tracked 文件 + 历史中新增的敏感文件名。  
**未打印任何 Secret 值。**

| 仓库 | 路径 | Commit | 规则 | 风险 | 说明 |
|------|------|--------|------|------|------|
| zerorealm-data | `docs/superpowers/plans/2026-07-29-agnes-media-pipeline.md` | `7f602a14d58f…` | generic_api_key_assignment | high | 文档中的 key 赋值；需人工确认是否为真实密钥 |
| zerorealm-data | `tests/test_agnes_client.py` | `94ad46c3ae1e…` | generic_api_key_assignment | high | 测试夹具风格赋值；倾向非生产密钥 |
| zerorealm-data | `.env.example` | `d4aed1cce450…` | sensitive_filename_added | medium | 模板文件名命中；预期存在 |

**未跟踪本地文件：** `.env` / `.env.local` 均被 gitignore，未进入 Git。此前报告的本地疑似真实密钥仍建议轮换（不计入本次 Git 扫描 FAIL）。

**网站仓：** 无同类命中。

---

## 8. 测试与 Build 复跑

| 检查 | 结果 |
|------|------|
| `zerorealm-data` `pytest` | **350 passed** |
| `zerorealm-data` `ruff check .` | **All checks passed** |
| `zerorealm-website` `npm test` | **33 passed** |
| `zerorealm-website` `npm run lint` | PASS |
| `zerorealm-website` `npm run build` | PASS（Next.js 16.2.12，含 metrics SSG） |

---

## 9. 结论

### PASS / FAIL

**PASS**

### 阻塞项

**无。**

### 非阻塞发布备注（不阻止 RC 结论）

1. 数据仓 7 个 commits、网站仓 2 个 commits 尚未按发布流程 push/merge（按此前要求未自动推送）。
2. Git 扫描 2 条 high 命中需人工复核；若确认文档含真实密钥，应轮换并清理历史后再公开分发。
3. 本地未跟踪 `.env` 建议轮换密钥。
4. 产品已知限制（非本 RC 回归失败）：企业/案例/信号公开页仍为空态；industry-map 硬编码未完全替换；未做真实微信/知乎外发。

### 本 RC 未做的事

- 未新增任何产品功能
- 未修改业务能力代码（仅生成本验收文档与一次性本地验证脚本）
- 未 commit / 未 push
