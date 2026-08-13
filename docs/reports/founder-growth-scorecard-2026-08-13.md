# Founder Growth Scorecard（founder_14d_2026-08-13）

> 生成日期：2026-08-13。仅聚合指标与手工漏斗计数；未复制原始报表，未记录用户 PII。目标为内部实验目标，非行业基准。**baseline_snapshot 只读参照；current_experiment 为当期台账；禁止跨周期漏斗。**

## baseline_snapshot（只读历史参照）

- 基线日期：2026-08-12
- 角色：`read_only_historical_reference`

### 微信（基线）

- “全部”唯一阅读人数：**90**
- 来源阅读人数合计（可重叠）：**103**
- 来源可否当作唯一人数：**否**（`sources_are_unique_people=false`）
- 分享人数：6
- 阅读原文人数：4
- 说明：历史基线只读参照。来源阅读人数可重叠，不可相加当作唯一人数。禁止用作当期漏斗分母。

### 知乎（基线）

- 阅读合计：305
- 互动合计（赞+藏+分享）：5+5+4
- 非零阅读日：11
- 文章级归因可用：**否**
- 说明：账号级日汇总；缺文章级归因。只读参照，非当期实验计数。

## current_experiment（当期实验）

- 周期：2026-08-13 ~ 2026-08-26
- 说明：仅含当期实验台账。channel counts 默认 null；impressions/views 未录入时对应率为 n/a；不得把 baseline_snapshot 人数当成分母。

### 当期渠道计数（默认 null，待录入）

- `wechat_unique_readers`: null
- `wechat_overlapping_source_readers_sum`: null
- `wechat_share_people`: null
- `wechat_original_link_people`: null
- `zhihu_reads`: null
- `zhihu_engagement`: null
- `zhihu_article_level_attribution_available`: False

### 当期漏斗计数（网站事件对齐）

- 字段：`impressions` / `views`（未录入默认 null）+`tool_views`（网站 `tool_view`）/ `subscribe_click` / `subscribe_success` / `interview_click` / `replies`；另保留 `interview_completed` / `public_case_permissions`。

- `impressions`: null
- `views`: null
- `tool_views`: 0
- `subscribe_click`: 0
- `subscribe_success`: 0
- `interview_click`: 0
- `replies`: 0
- `interview_completed`: 0
- `public_case_permissions`: 0

### 当期漏斗转化率（零/缺失分母 → n/a）

- `impression_to_view`: n/a (zero/missing denominator)
- `view_to_tool`: n/a (zero/missing denominator)
- `tool_to_subscribe_click`: n/a (zero/missing denominator)
- `subscribe_click_to_success`: n/a (zero/missing denominator)
- `tool_to_interview_click`: n/a (zero/missing denominator)
- `interview_click_to_reply`: n/a (zero/missing denominator)

## 内部实验目标（非行业基准）

- `wechat_unique_readers_14d`: 相对本基线周均提升 ≥20%（小样本，仅作实验目标）
- `wechat_share_or_original_link`: 14天内分享+阅读原文合计 ≥ 8（内部实验目标，非行业基准）
- `zhihu_nonzero_read_days`: 14天内非零阅读日 ≥ 10（内部实验目标，非行业基准）
- `cta_events`: 订阅/纠错/访谈意向合计 ≥ 5（人工计数）（内部实验目标，非行业基准）
- `zhihu_reads_14d`: ≥ 350（相对本基线窗口 305 的温和抬升目标）（内部实验目标，非行业基准）
- `zhihu_engagement_14d`: 赞+藏+分享合计 ≥ 12（内部实验目标，非行业基准）

## 告警

- [warning] `wechat_source_overlap` scope=baseline_snapshot: 基线参照：微信来源阅读人数合计 103 ≠ “全部”唯一阅读 90；来源可重叠，禁止相加当作唯一人数。（此为 baseline_snapshot，不作当期漏斗分母）
- [warning] `zhihu_missing_article_attribution` scope=baseline_snapshot: 基线参照：知乎仅为账号级日汇总，缺少文章级归因；不可对单篇内容下因果结论。
- [warning] `zhihu_missing_article_attribution` scope=current_experiment: 知乎仅为账号级日汇总，缺少文章级归因；不可对单篇内容下因果结论。

## 局限

- 样本小，禁止从小样本推因果。
- 微信重叠来源不可当唯一人数。
- 知乎缺文章级归因。
- 禁止跨周期漏斗：基线人数不可作当期分母。
- 当期 impressions/views 未录入或分母为 0 时转化率为 n/a。
- 漏斗事件字段对齐网站 tool_view / subscribe_click / subscribe_success / interview_click。
- 目标为内部实验目标，不是行业基准。
