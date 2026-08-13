# 双保险无 LLM 每日采集

每天只做一次采集链路：**抓取 → 规则清洗 → 去重 → digest**。
**不需要网站常驻进程。** 云端保连续，本机开机/可选 23:00 补充。

| 通道 | 触发 | 作用 |
|------|------|------|
| GitHub Actions `daily-crawl.yaml` | cron `0 15 * * *`（北京 23:00）+ `workflow_dispatch` | 云端主采集，保连续 |
| macOS launchd + `run_local_collection.sh` | **开机 RunAtLoad**（补充）+ 可选本机 23:00 | 本机补漏，不依赖网站 |

两边都只调用 `main.py --local-only`，绝不生成内容/图片、不发布推送。

## 运行时保护（防御纵深）

瘦身 `Daily Collection` YAML 已在远端生效（`collect` 与 `contract-check` 并行，无 generate/publish）。
仍保留进程级闸门，避免旧 Pipeline 或误注入 secret 时走 LLM/发布：

| 触发 | 行为 |
|------|------|
| `GITHUB_ACTIONS=true` 且执行 `main.py` | 无条件等效 `--local-only`；向 `GITHUB_ENV` 写入 `SYNC_PUBLIC_BUNDLE=false` 等关闭项并清空微信/网站 token。**不记录原值。** |
| `GITHUB_ACTIONS=true` 且执行 `generate_daily.py` | 在任何 LLM key 检查/调用之前打印跳过原因并 **exit 2** |
| 本机 / 无 `GITHUB_ACTIONS` | 行为不变；手动 `generate_daily.py` / `run_daily.py` 仍走 legacy |

本机 launchd / `run_local_collection.sh` 不受影响。

## 做什么 / 不做什么

| 定时采集会做 | 定时采集绝不做 |
|--------------|----------------|
| `main.py --local-only` 联网采集源 | 调用 DeepSeek / OpenAI / Anthropic / Gemini / Agnes 等项目内外部 LLM API |
| 规则去重 / 质量 / digest | `generate_daily.py` / 自动日报 |
| 写入 `data/` 与 `logs/`（云端另上传 artifact + `data/state` cache） | 生图、发布、推送、微信草稿、网站 push |
| 本机写 `latest_status.json` / `latest_handoff.md` | `git push` / `cursor-agent` / `agy` / Supabase |

需要 LLM 的后续工作只能通过工作区根目录执行工具：

```bash
/Users/Logan/AICoding/ZeroRealmAI/scripts/ai-delivery.sh zerorealm-data "<task>"
```

- Cursor 实现：`--model auto`
- Antigravity 测试验收与生图：`gemini-3.6-flash-medium`
- 位图只由 Antigravity 生成

## 本机手动跑一次

```bash
./scripts/run_local_collection.sh
./scripts/run_local_collection.sh 2026-08-13
# 或
LOCAL_COLLECTION_DATE=2026-08-13 ./scripts/run_local_collection.sh
```

脚本会：

1. `set -euo pipefail` + 目录锁防重入；
2. 用北京时间日期（`TZ=Asia/Shanghai`）；
3. 优先 `.venv/bin/python`；
4. `unset` LLM / 微信 / 网站 / Supabase 等密钥；
5. 仅调用 `main.py --local-only --date DATE`；
6. 更新：
   - `logs/local_collection/latest_status.json`
   - `logs/local_collection/latest_handoff.md`
   - `logs/local_collection/run_YYYY-MM-DD.log`

## macOS launchd（资产在仓库内；默认不自动安装）

```bash
# 安装（幂等；会写 ~/Library/LaunchAgents，并渲染绝对路径）
./scripts/macos/install_local_collection_launchd.sh

# 卸载
./scripts/macos/uninstall_local_collection_launchd.sh
```

- 模板：`scripts/macos/com.zerorealm.local-collection.plist.template`
- `__REPO_ROOT__` 在安装时替换为当前 repo **绝对路径**（模板内无硬编码 `/Users/...`）
- `RunAtLoad=true`：开机时补充
- `StartCalendarInterval` 23:00：本机可选每日补跑（Mac 时区请设为北京时间 / `TZ=Asia/Shanghai`）
- 标准输出/错误写入 `logs/local_collection/launchd.*.log`
- CI / 验收测试**不会**实际安装或写 `$HOME`

## 云端 workflow

`.github/workflows/daily-crawl.yaml`：

- 保留 `schedule: cron: '0 15 * * *'` 与 `workflow_dispatch`
- **两 job 并行**：`collect` 是主采集，**不** `needs` `contract-check`；契约 smoke 失败不能跳过爬虫
- `collect`：checkout → setup-python（pip cache）→ 带 retry 的 `pip install -r requirements.txt` → 解析日期 → restore `data/state` → `python main.py --local-only --date` → 健康门写 summary → 始终上传 `data/`/`logs/` artifact
- **不**安装 Playwright Chromium，**不**在 collect 跑 pytest / 全量测试
- `contract-check`（可选、并行）：只跑 `tests/test_daily_collection_contract.py` 与 `tests/test_collection_health.py`；job 级 `continue-on-error` 让失败可见，但不掩盖 `collect`、也不改采集结论
- **无** `generate_daily` / `publish` / 生图 / 网站 push / 微信草稿 / LLM 或敏感 secret 注入

### 旧失败根因

历史 workflow 把全量 pytest（约 554）、Playwright 浏览器、生成/发布绑在采集步骤之前。任一步失败（GitHub API 确认 run `31615607142` 在第 5 步 `Run tests` 失败）会使后续 crawler **被跳过**。当时无管理员 token，无法下载完整日志，但结构本身足以解释“测试红 → 当天没采集”。

### 新容错边界

| 情况 | 结果 |
|------|------|
| `main.py` 系统级异常（配置损坏、管线崩溃） | 进程退出非 0；`collect` 失败；**不用** `continue-on-error` 掩盖 |
| 单个/部分来源失败（含未装 Chromium 的 JS 源） | 记入 metrics；**至少 1 个启用源成功**则健康门通过 |
| 全部启用源失败，或没有/损坏的 metrics | `scripts/check_collection_health.py` 失败，`collect` 失败 |
| `contract-check` 失败 | Actions 上可见；**不跳过**采集；workflow 结论跟 `collect` |
| summary / artifact | `if: always()`；artifact 名在日期步骤失败时回退 `github.run_id`；`if-no-files-found: warn` |

健康门把 `sources_success` / `sources_failed` / `items_new` / `errors` 写入 `GITHUB_STEP_SUMMARY`。本地/CI 单测不联网。

## Status / handoff 契约（本机）

`latest_status.json`（`schema_version: 1`）关键字段：

- `mode`: 恒为 `"local-only"`
- `status`: `running` | `ok` | `error` | `locked`
- `date`, `started_at`, `finished_at`, `exit_code`
- `command`: `["main.py", "--local-only", "--date", "<DATE>"]`
- `log_path` / `status_path` / `handoff_path` / `digest_hint`
- `forbidden_in_this_job`: 生成/发布/推送/外部 LLM 等
- `next_llm_work`: ai-delivery 路径与模型约定

## Legacy

- `run_daily.py`：手动 legacy 内容管线（采集+生成+本地复制），**不是**每日定时入口，也不是调度器。
- `.env` 中 DeepSeek 等外部 LLM 配置：legacy / test-only，定时采集不会使用。
