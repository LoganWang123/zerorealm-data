# 周决策清单（founder_14d_2026-08-13）

> 本决策清单用于单人创始人周运营，不构成因果证明，目标为内部实验目标而非行业基准。

- 生成日期：2026-08-15
- 预估工时/周：11.5h（预算 8–15h）

## 决策

### P1 · use_unique_readers_only

- 决策：周复盘只采用微信“全部”唯一阅读人数，不将来源渠道相加。
- 依据：来源归因可重叠；baseline_snapshot.wechat.sources_are_unique_people=false。

### P1 · zhihu_trend_only

- 决策：知乎只观察账号级趋势与非零阅读日，不对单篇下因果结论。
- 依据：zhihu_missing_article_attribution 告警生效中。

### P1 · no_auto_publish

- 决策：所有微信/知乎内容人工审核后发布；命令只生成计划与台账，不触发发布。
- 依据：combat_pack 全部 auto_publish=false。

### P2 · prefer_tool_checklist_content

- 决策：本周内容优先五指标复盘 / 缺货排查 / 运营决策清单，不主推泛日报搬运。
- 依据：作战包主题与内部实验目标对齐；小样本仅作实验假设。

### P2 · fill_manual_funnel

- 决策：只录入可匿名观测台账：内容按期准备率、关键词「复盘表」回复数、工具页访问、公开平台收藏/赞同/阅读变化；以及 impressions/views 与 subscribe_click/subscribe_success；零或缺失分母转化率记为 n/a；禁止把基线人数当当期分母；不记录访谈线索。
- 依据：当前 n/a 槽位: impression_to_view, view_to_tool, tool_to_subscribe_click, subscribe_click_to_success。

### P2 · use_piece_cta_url

- 决策：发布时粘贴该条可复制 CTA URL（工具页 + 本条 UTM）；文案唯一行动为回复「复盘表」或打开自助工具。
- 依据：combat_pack 每条含 cta_url，禁止再用访谈 CTA。

### P3 · self_serve_funnel_only

- 决策：转化只走公开内容 → 关注公众号 → 回复「复盘表」→ 自助周复盘工具；可公开订阅；禁止一对一联系、加微信、访谈或索取公司/点位身份。
- 依据：创始人仍在智能柜公司任职，不适合开展运营商访谈。

## 漏斗转化率

- `impression_to_view`: n/a (zero/missing denominator)
- `view_to_tool`: n/a (zero/missing denominator)
- `tool_to_subscribe_click`: n/a (zero/missing denominator)
- `subscribe_click_to_success`: n/a (zero/missing denominator)

## 告警

- [warning] `wechat_source_overlap`: 基线参照：微信来源阅读人数合计 103 ≠ “全部”唯一阅读 90；来源可重叠，禁止相加当作唯一人数。（此为 baseline_snapshot，不作当期漏斗分母）
- [warning] `zhihu_missing_article_attribution`: 基线参照：知乎仅为账号级日汇总，缺少文章级归因；不可对单篇内容下因果结论。
- [warning] `zhihu_missing_article_attribution`: 知乎仅为账号级日汇总，缺少文章级归因；不可对单篇内容下因果结论。
