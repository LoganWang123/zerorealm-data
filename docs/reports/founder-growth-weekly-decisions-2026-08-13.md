# 周决策清单（founder_14d_2026-08-13）

> 本决策清单用于单人创始人周运营，不构成因果证明，目标为内部实验目标而非行业基准。

- 生成日期：2026-08-13
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

- 决策：只录入当期台账：impressions/views 与网站事件 tool_views(tool_view)/subscribe_click/subscribe_success/interview_click/replies；零或缺失分母转化率记为 n/a；禁止把基线人数当当期分母。
- 依据：当前 n/a 槽位: impression_to_view, view_to_tool, tool_to_subscribe_click, subscribe_click_to_success, tool_to_interview_click, interview_click_to_reply。

### P2 · use_piece_cta_url

- 决策：发布时粘贴该条可复制 CTA URL（工具页 + 本条 UTM）；订阅/访谈入口在工具页内。
- 依据：combat_pack 每条含 cta_url，禁止只用泛化文案。

### P3 · outreach_empty_slots

- 决策：填写本周 3–5 个目标账户空槽；无对象则保持空白，禁止虚构名称。
- 依据：外联是漏斗后段唯一来源，且不得自动发布。

## 漏斗转化率

- `impression_to_view`: n/a (zero/missing denominator)
- `view_to_tool`: n/a (zero/missing denominator)
- `tool_to_subscribe_click`: n/a (zero/missing denominator)
- `subscribe_click_to_success`: n/a (zero/missing denominator)
- `tool_to_interview_click`: n/a (zero/missing denominator)
- `interview_click_to_reply`: n/a (zero/missing denominator)

## 告警

- [warning] `wechat_source_overlap`: 基线参照：微信来源阅读人数合计 103 ≠ “全部”唯一阅读 90；来源可重叠，禁止相加当作唯一人数。（此为 baseline_snapshot，不作当期漏斗分母）
- [warning] `zhihu_missing_article_attribution`: 基线参照：知乎仅为账号级日汇总，缺少文章级归因；不可对单篇内容下因果结论。
- [warning] `zhihu_missing_article_attribution`: 知乎仅为账号级日汇总，缺少文章级归因；不可对单篇内容下因果结论。
