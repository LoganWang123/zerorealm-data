# 创始人增长运营系统（微信 / 知乎）

单人创始人每周 **8–15 小时** 的可重复运营回路。只消费隐私安全的聚合基线与手工漏斗计数，**不复制**原始报表，不记录用户 PII，**不自动发布**。

## 前置

1. 已有基线（或先从本地报表只读生成，报表本身不入库）：

```bash
python scripts/build_channel_growth_baseline.py \
  --wechat-xls "/path/to/tendency.xls" \
  --zhihu-csv "/path/to/zhihu-daily.csv"
```

2. 依赖见 `requirements.txt`（含 `xlrd`、`jsonschema`）。

## 一条命令：漏斗 + 周决策 + 作战包

```bash
python scripts/generate_founder_growth_ops.py \
  --baseline-json data/growth/channel-baseline-2026-08-12.json \
  --write-templates \
  --start-date 2026-08-13 \
  --out-dir data/growth/ops-out
```

产出：

| 产物 | 路径 |
| --- | --- |
| 实验台账 schema | `data/growth/experiment-ledger.schema.json` |
| 实验台账模板 | `data/growth/experiment-ledger.template.json` |
| Scorecard / 漏斗 / 决策 | `data/growth/ops-out/` |
| 14 天作战包（报告） | `docs/reports/founder-growth-combat-pack-2026-08-13.md` |
| Scorecard（报告） | `docs/reports/founder-growth-scorecard-2026-08-13.md` |
| 周决策（报告） | `docs/reports/founder-growth-weekly-decisions-2026-08-13.md` |
| 访谈/案例模板 | `docs/operations/founder-growth-outreach-templates.md` |

填写**当期**台账后可再跑：

```bash
python scripts/generate_founder_growth_ops.py \
  --ledger-json data/growth/experiment-ledger.filled.json
```

## 运营复盘（技术采集 vs 渠道业务，含新鲜度闸门）

渠道结果过期时，**不要**把 baseline 唯一阅读写入 `current_experiment`。只读导入本地报表并生成分列复盘：

```bash
python scripts/build_ops_retrospective.py \
  --review-date 2026-08-15 \
  --import-dir "/path/to/Downloads" \
  --baseline-json data/growth/channel-baseline-2026-08-12.json \
  --collection-snapshot-json data/growth/collection-run-31817014485.json
```

- `--import-dir` 会选择最新 `tendency_*.xls`；知乎优先 `日报表 (1).xls`，若已改名为 `日报表.xls` 则使用该文件。
- 报表 `period.end` 距复盘日超过 1 天视为 stale；stale 报表 **拒绝** 填入当期渠道计数。
- 产出只含聚合指标与 run 元数据，不复制原始报表。

## 口径硬规则

- **禁止跨周期漏斗**：`baseline_snapshot` 只读历史参照；`current_experiment` 才是当期台账。默认生成时 `channel_observed` 为 `null`、事件 counters 为 `0`；**不得**把基线微信 unique 等人数当作当期漏斗分母。
- 微信 **“全部”** = 唯一阅读人数；搜一搜/推荐等 **可重叠**，禁止相加。
- 知乎默认 **无文章级归因** → scorecard / 台账会打出 `zhihu_missing_article_attribution` 告警。
- 台账事件字段对齐网站：`tool_views`（网站 `tool_view`）、`subscribe_click`、`subscribe_success`、`interview_click`，另有 `impressions` / `views` / `replies`；可保留 `interview_completed` / `public_case_permissions`。
- 漏斗率：`impression_to_view`、`view_to_tool`、`tool_to_subscribe_click`、`subscribe_click_to_success`、`tool_to_interview_click`、`interview_click_to_reply`；**零或缺失分母**为 `n/a`，不是 `0%`。
- 作战包每条内容给出可复制 **CTA URL**：`https://zerorealm.tech/tools/smart-cabinet-weekly-review` + 该条 UTM；订阅/访谈入口在工具页内。
- 量化目标是 **内部实验目标**，不是行业基准。
- 不从小样本推因果；命令不触发任何渠道发布。

## 周节奏（摘要）

1. 按作战包写 微信工具/清单文 + 知乎改写；粘贴该条 CTA URL（含 UTM）。
2. 每周维护 3–5 个 **空** 目标账户槽位（不虚构名称）。
3. 只更新**当期**台账手工漏斗与渠道计数，跑生成命令看 scorecard 与周决策。
4. 复盘只对照内部实验目标与告警；区分 baseline_snapshot 与 current_experiment。

## 测试

```bash
python -m pytest -q tests/test_founder_growth_ops.py tests/test_channel_growth_baseline.py tests/test_ops_retrospective.py
python -m pytest -q
ruff check growth scripts/generate_founder_growth_ops.py scripts/build_channel_growth_baseline.py scripts/build_ops_retrospective.py tests/test_founder_growth_ops.py tests/test_ops_retrospective.py
```
