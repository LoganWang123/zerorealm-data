# Local Release Run 01

日期：2026-08-08（本地集成运行）  
范围：数据仓 → Public Bundle → 网站 → Search/SEO → MediaJob  
约束：不 push / 不 merge / 不 Production / 不微信正式发 / 不知乎发 / 不改 draft 为 approved / 不调用 Agnes

## DATA

| 项 | 结果 |
|----|------|
| HEAD | `37c5263` |
| `ruff check .` | PASS |
| `pytest` | **365 passed** |
| Export | `dist/public-v1/` |
| contractVersion | `1.0` |
| counts | metrics=15, companies=0, cases=0, signals=0, sources=0, claims=0, topics=0 |
| bundleHash | `sha256:9a0908107ec2e42233238142ae009ad2f7cddd07fbaecf8748aa2f83d1f77295` |
| file hashes | 全部匹配 |
| draft companies 进入 Bundle | **否** |
| reviewing signals 进入 Bundle | **否** |
| draft cases 进入 Bundle | **否** |

## WEBSITE

| 项 | 结果 |
|----|------|
| Bundle 同步 | 本地 `Copy-Item` → `data/public-v1`（与 data `dist/public-v1` manifest/文件一致） |
| `npm test` | **40 passed** |
| `npm run lint` | PASS |
| typecheck | 经 `next build` TypeScript 检查 PASS（无独立 `typecheck` script） |
| `npm run build` | PASS（含 metrics SSG 15 项） |
| Local URL | **http://localhost:3000** |
| Network | http://192.168.31.183:3000 |

### Page smoke（HTTP 200 + 关键断言）

| Path | 结果 |
|------|------|
| `/` | 200；标题含 ZeroRealm AI｜零域 |
| `/metrics` | 200；含缺货率与 15 |
| `/metrics/stockout-rate` | 200；口径说明；SEO title 正确 |
| `/companies` | 200；空态「企业库正在持续核验中…」 |
| `/cases` | 200；空态「案例库正在建设中…」 |
| `/signals` | 200；空态「暂时没有已通过审核的行业信号…」 |
| `/search?q=缺货` | 200；命中缺货率 |
| `/research/industry-map` | 200；provenance/legacy 可见 |
| `/daily/2026-08-01` | 200 |
| `/sitemap.xml` | 200；含 metrics/search |
| `/robots.txt` | 200 |
| `/opengraph-image` | 200；`image/png` |
| 中文乱码 | 未发现 U+FFFD |
| Console warnings/errors（Playwright） | 0 warning / 0 error（本次会话采样） |

## CONTENT（catalog 状态，未为展示改写）

| 项 | 数量 |
|----|------|
| approved metrics | 15（已进 Bundle） |
| draft companies | 52（未进 Bundle） |
| draft cases | 3（未进 Bundle） |
| reviewing signals | 6（未进 Bundle） |

## MEDIA

| 项 | 结果 |
|----|------|
| current IDE | Cursor |
| image generated | 是（IDE native GenerateImage） |
| MediaJob | `mj-5a4a3a0307b8` |
| attach | 成功 |
| validation | passed |
| review status | **pending_review**（未 auto-approve） |
| canPublish | false |
| Agnes invocation | **0** |
| Agnes fallback | 无 |

## E2E

1. Research catalog → `export_public_bundle` → website `data/public-v1` → pages/search：**PASS**
2. ResearchBrief test → `export_content_package` → `dist/content-package/local-release-run-01/`：**PASS**（含 website/wechat/zhihu/sources/media/metadata.json）
3. ImageBrief → IDE image → MediaJob attach/validate → pending_review：**PASS**

## LOCAL RELEASE STATUS

**PASS**

## Notes

- 本次运行生成的 `dist/`、`output/`、网站侧同步后的 `data/public-v1` 差异：**不作为正式 commit 提交**（按任务要求）。
- Dev server 已在后台运行：`npm run dev` @ `http://localhost:3000`
- 若进程已停，重启命令：在 `zerorealm-website` 目录执行 `npm run dev`
