# 运营复盘（2026-08-15）

> 技术采集指标与微信/知乎业务指标分列。未复制原始报表，未记录用户 PII。不过期数据不编造成果。

- 生成日期：2026-08-15
- 原始报表入库：**否**（`raw_reports_copied=False`）
- 虚构成果：**否**（`fabricated_outcomes=False`）

## A. 技术采集（GitHub Actions Daily Collection）

- 性质：technical_collection；**不是**微信/知乎经营结果
- run：`31817014485` https://github.com/LoganWang123/zerorealm-data/actions/runs/31817014485
- event：`schedule`  conclusion：**success**
- 采集日期：2026-08-14
- head_sha：`be4739b5876f49294c98a2c5a642a906c2e623d8`
- 工作流耗时：1119s；crawl `1083.6`s
- sources_total：51
- sources_success：34
- sources_failed：17
- items_new：249；items_total：1166；items_duplicate：917
- artifact：daily-collection-2026-08-14 id=9225967842 bytes=514402
- 失败源：36kr_rss: no items returned, linkshop_web: no items returned, ebrun_alt: no items returned, hema_web: no items returned, dingdong_web: no items returned, easivend_web: no items returned, hetun_web: no items returned, hikvision_web: no items returned, quectel_web: no items returned, wantwant_web: no items returned, 3squirrels_web: no items returned, vanke_web: no items returned, crland_web: no items returned, samr_web: no items returned, ccfa_web: no items returned, xinhua_web: no items returned, ccgp_web: no items returned

## B. 微信 / 知乎业务指标（只读聚合）

### 数据新鲜度

- 微信报表 `tendency_1783969521_1786475121.xls` 周期 2026-07-14~2026-08-12；lag_days=3；status=**stale**；covers_experiment_start=False
- 知乎报表 `日报表 (1).xls` 周期 2026-07-27~2026-08-13；lag_days=2；status=**stale**
- 与基线聚合是否一致：微信 True，知乎 True；new_outcome_window=False
- current_experiment 导入：applied=**False**；wechat period_end 2026-08-12 status=stale; refusing to copy baseline unique readers into current_experiment

### 微信（“全部”=唯一阅读）

- 全部唯一阅读人数：**90**
- 搜一搜（可重叠）：47
- 推荐（可重叠）：31
- 分享人数：6；阅读原文：4；发表篇数：12
- “全部”为唯一阅读人数；来源可重叠，禁止相加。

### 知乎（账号级日汇总）

- 阅读合计：**305**
- 赞/藏/分享：5/5/4
- 非零阅读日：11；峰值 2026-08-09=53
- 未选用的等价文件：日报表.xls
- 账号级日汇总；缺文章级归因。

### 当期实验台账（禁止用基线当分子分母）

- `wechat_unique_readers`: null
- `wechat_overlapping_source_readers_sum`: null
- `wechat_share_people`: null
- `wechat_original_link_people`: null
- `zhihu_reads`: null
- `zhihu_engagement`: null
- `zhihu_article_level_attribution_available`: False

### 官网漏斗（无本地导出则不虚构）

- 官网工具页已埋点 tool_view / subscribe_click / keyword_replies（PostHog）；本仓库无 PostHog 导出。漏斗保持手工计数，不虚构。
- `impressions`: null
- `views`: null
- `tool_views`: 0
- `subscribe_click`: 0
- `subscribe_success`: 0
- `keyword_replies`: 0
- `replies`: 0
- `keyword_replies`: 0
- `public_case_permissions`: 0

### 漏斗转化率

- `impression_to_view`: n/a (zero/missing denominator)
- `view_to_tool`: n/a (zero/missing denominator)
- `tool_to_subscribe_click`: n/a (zero/missing denominator)
- `subscribe_click_to_success`: n/a (zero/missing denominator)
- `tool_to_keyword_replies`: n/a (zero/missing denominator)
- `keyword_replies_to_reply`: n/a (zero/missing denominator)

## C. 下一步（单一最高优先级，已落地自动化）

- ID：`import_fresh_channel_reports_7d`
- Owner：founder（GitHub `LoganWang123`）
- 动作：导入覆盖当期实验窗口的微信/知乎新报表，经 freshness 闸门后再填 current_experiment
- 7 日指标：`fresh_wechat_report_covers_current_experiment` — 新微信 tendency 的 period.end 距复盘日 ≤1 天，且 covers_experiment_start=true，且 current_experiment.channel_observed.wechat_unique_readers 非 null
- Continue：导入覆盖 2026-08-13 之后的微信“全部”唯一阅读；禁止把基线 unique_readers 当当期分母
- Stop：到 2026-08-22 仍只有 period.end≤2026-08-12 的微信报表→ 停止把 14 天实验当作可量化增长结论；工具/清单文可继续人工发布，但不声称阅读提升
- 下次复盘：2026-08-22
- 依据：渠道结果数据已过期；采集健康不能替代微信/知乎业务结果。 实验窗口至 2026-08-26。
- 节奏决议（同日）：拒绝默认「一周一篇微信」；执行计划见 `docs/reports/ceo-publish-distribution-plan-2026-08-15.md`（微信约 2 篇工具/清单/周 + 知乎 1 篇改写/周）。

## 局限

- 未复制原始报表，未记录用户 PII。
- 技术采集指标与微信/知乎业务指标分列，禁止混用。
- 报表过期时不把 baseline unique readers 写入 current_experiment。
- 官网漏斗无本地事件导出时保持 0 / n/a，不虚构转化。
- 小样本禁止因果结论；目标为内部实验目标。
