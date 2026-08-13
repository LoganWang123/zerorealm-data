# ZeroRealm Data

零售行业数据采集、知识处理、内容生成与渠道发布系统 —— ZeroRealm AI 的研究与内容生产后端。

仓库地址：`https://github.com/LoganWang123/zerorealm-data`

## Quick Start

```bash
git clone https://github.com/LoganWang123/zerorealm-data.git
cd zerorealm-data
pip install -r requirements.txt
python main.py --source 36kr_rss
```

## 输出目录

```text
data/raw/       ← 原始 JSON
data/clean/     ← 清洗后 Markdown
data/digest/    ← 每日日报素材
output_daily/   ← 生成的日报 MDX（本地，默认不入库；需手动/IDE 触发）
dist/public-v1/ ← Public Content Bundle（后续阶段导出）
logs/local_collection/  ← 本机定时采集 status / handoff / 运行日志
```

## CLI

```bash
python main.py                                      # 采集全部已启用源
python main.py --source 36kr_rss                    # 采集一个源
python main.py --source 36kr_rss,ubox_web           # 采集指定源集合
python main.py --date 2026-08-01 --source 36kr_rss  # 指定输出日期
python main.py --local-only                         # 仅写本机 data/logs，跳过 Supabase
python main.py --debug                              # 详细日志

# 推荐的每日本机采集入口（北京时间日期、禁 LLM/发布密钥）
./scripts/run_local_collection.sh
./scripts/run_local_collection.sh 2026-08-13

# Legacy / 手动内容管线（非定时入口）
python generate_daily.py --date 2026-08-06          # 生成日报 MDX（需外部 LLM，legacy/test）
python run_daily.py --date 2026-08-06               # 手动 legacy：采集 + 生成 + 本地复制（默认不 push）
```

## 运行范围

完整白名单维护在 `config/sources.yaml`。本机每日采集运行所有已启用源；
先完成连续稳定性验证，再逐步扩大范围。

## 架构

```text
GitHub Actions cron 0 15 (北京 23:00) ──云端保连续──┐
macOS launchd (开机补充 + 可选 23:00) / run_local_collection.sh ─┐
    → main.py --local-only
    → Crawler (RSS / HTML / JS / API)  [可联网]
    → Dedup + Quality（规则，无 LLM）
    → Writer (JSON / Markdown) + Digest
    → data/ + logs/（本机另写 status/handoff；云端上传 artifact）
    →（人工）Cursor Auto 实施内容工作；Antigravity 验收/生图
```

研究领域模型（`research/`）与 Public Bundle 契约正在渐进接入；现有
`Article` + `PublishWorkflow` 继续作为微信等渠道的发布交换层。详见
[ADR 0001](docs/adr/0001-research-public-bundle.md)。

## 每日采集（双保险，无 LLM）

每天一次采集链路；**网站不用常驻**。云端保连续，本机补充。定时任务**绝不**调用
项目内 DeepSeek / OpenAI / Anthropic / Gemini / Agnes 等外部 LLM API，也不自动
生成日报、生图、发布、推送或建微信草稿。

| 入口 | 作用 |
|------|------|
| `.github/workflows/daily-crawl.yaml` | 云端主采集：cron `0 15`（北京 23:00）+ 手动；`collect` 与契约 smoke 并行且互不阻塞；仅 `--local-only` + 健康门 + artifact + dedup cache；不装 Playwright 浏览器、不跑全量测试。`GITHUB_ACTIONS=true` 时 `main.py` 强制 local-only 并写 `GITHUB_ENV` 关闭发布，`generate_daily.py` exit 2 跳过 LLM |
| `./scripts/run_local_collection.sh` | 本机采集入口（锁、禁密钥、`--local-only`） |
| `scripts/macos/install_local_collection_launchd.sh` | 可选安装 launchd（开机补充 + 可选 23:00；幂等渲染绝对路径） |
| `python run_daily.py` | **手动 legacy**，非调度入口 |

采集完成后，需要 LLM 的工作只能通过工作区根目录执行工具：

```bash
/Users/Logan/AICoding/ZeroRealmAI/scripts/ai-delivery.sh zerorealm-data "<task>"
```

- Cursor 实现模型：`auto`
- Antigravity 测试验收与生图：`gemini-3.6-flash-medium`
- 位图只由 Antigravity 生成（Cursor 只准备 brief / 路径 / 集成代码）

详见 [双保险本地采集](docs/operations/local-collection.md)。


## 本地媒体生成（Agnes 生图已停用）

**Agnes 不再用于任何图片生成。** 生产图片由 **Antigravity**（`gemini-3.6-flash-medium`）完成。
程序化模板 / `ZEROREALM_LOCAL_IMAGE_CMD` 仅作兼容；无本地模型时写入
`dist/media-jobs/` prompt package（`pending_local_generation`），**不会** fallback 到 Agnes。

```bash
python scripts/generate_local_media.py <content-id> --channel wechat --purpose cover
python scripts/generate_local_media.py <content-id> --prompt-only
```

公众号素材仍须人工审核（SHA 绑定）：

```bash
python review_media.py --date YYYY-MM-DD \
  --approve cover=<SHA256> \
  --approve body_1=<SHA256> \
  --approve body_2=<SHA256> \
  --approve body_3=<SHA256>
```

`generate_media.py homepage` 与 `AGNES_API_KEY` 仅保留为历史兼容/文档说明，
生产路径会拒绝 Agnes 生图。详见
`docs/reports/agnes-image-generation-deprecation.md`。

## 创始人增长运营（微信 / 知乎）

单人创始人每周 8–15 小时的 scorecard、14 天作战包、手工漏斗与周决策。
只读本地原始报表生成聚合基线，**不复制 raw/PII，不自动发布**。

```bash
# 1) 只读原始报表 → 聚合基线（报表本身不入库）
python scripts/build_channel_growth_baseline.py \
  --wechat-xls "/path/to/tendency.xls" \
  --zhihu-csv "/path/to/zhihu-daily.csv"

# 2) 一条命令：漏斗转化率 + 周决策 + 作战包 / 访谈槽位
python scripts/generate_founder_growth_ops.py \
  --baseline-json data/growth/channel-baseline-2026-08-12.json \
  --write-templates \
  --start-date 2026-08-13
```

口径：禁止跨周期漏斗（baseline 只读，当期 channel 默认 null）；
微信来源可重叠不可当唯一人数；知乎缺文章级归因会告警；
台账对齐网站 `tool_view` / `subscribe_click` / `subscribe_success` / `interview_click`；
漏斗零/缺失分母为 `n/a`；作战包每条含可复制工具页 CTA URL+UTM；
目标为内部实验目标而非行业基准。
详见 [founder-growth-ops.md](docs/operations/founder-growth-ops.md)。

## 验证

```bash
python -m pytest -q
ruff check .
```

## 关联文档

- [双保险无 LLM 每日采集](docs/operations/local-collection.md)
- [Founder Growth Ops](docs/operations/founder-growth-ops.md)
- [ADR 0001 — Research + Public Bundle](docs/adr/0001-research-public-bundle.md)
- [Data Strategy V1.1](../公司规划/数据采集/Data%20Strategy%20V1.0.md)
- [M1 Data Demo Plan V1.2](../公司规划/数据采集/M1%20Data%20Demo%20Plan.md)
- [TDD — Data Crawler V1.2](../公司规划/数据采集/TDD.md)
