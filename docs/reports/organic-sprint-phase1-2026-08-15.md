# Organic sprint phase 1 packets · 2026-08-15

- Status: `phase1_external_ops_recorded`
- Image status: `awaiting_antigravity_images`
- External API mutation (repo): `False`
- Browser manual ops: `True`
- LLM API: `False`
- Friends circle / groups / private: forbidden
- Secrets policy: no CDN URLs / login tokens / cookies recorded; no Antigravity account/email or quota recovery clock
- Conversion: `公开内容 → 关注公众号 → 回复「复盘表」→ 自助使用周经营复盘工具；可公开订阅，无一对一/加微信/访谈`
- Professional boundaries: declared in packet compliance
- Truthfulness: WeChat autoreply `configured`/`enabled`; 缺货贴图计划 `canceled` (`same_channel_topic_overlap_with_2026-08-15_article`；草稿/5图/provenance 保留)；单点贡献稿 `production_ready_revision` / `external_sync_pending`；Zhihu external draft accepted (`draft_saved`, `revision_pending=false`, `publish_blocked=false`, `employment_boundary_synced=true`); `legacy_interview_cta_status=deleted`; historical `antigravity_quota_temporarily_exhausted` resolved

## Packets

1. **WeChat 单点贡献修订** `2026-08-15` 《点位有销量却不赚钱？用一张周表算清单点贡献》
   - piece_id: `o1-wechat-point-contribution`
   - status: `production_ready_revision`
   - external_sync_status: `external_sync_pending`（不得标已同步/已发布/已定时）
   - packet: `data/growth/content-packet-o1-wechat-point-contribution-2026-08-15.json`
   - agy handoff: `docs/reports/wechat-point-contribution-revision-2026-08-15.md`
   - CTA: 回复「复盘表」打开周经营复盘工具

2. **WeChat 贴图（已取消发布计划）** `2026-08-17` 《柜机缺货先查这7步》
   - piece_id: `o1-wechat-stockout-tieku`
   - tracking: `organic_20260817_wechat_tieku_stockout7`
   - packet: `data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json`
   - image briefs: 5（保留；不删除）
   - image_status: `images_ready`
   - external_status: `canceled`
   - cancel_reason: `same_channel_topic_overlap_with_2026-08-15_article`
   - draft_status: `draft_saved`（外部草稿保留）
   - employment_boundary_synced: `true`
   - scheduled / published: `false`

3. **Zhihu 场景改写** `2026-08-18` 《库存显示有货，为什么柜机还是缺货？》
   - piece_id: `o1-zhihu-inventory-stockout`
   - tracking: `organic_20260818_zhihu_inventory_stockout`
   - packet: `data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json`
   - external draft id: `2072013992894149965`
   - external_status: `draft_saved`
   - revision_pending: `false`
   - employment_boundary_synced: `true`
   - publish_blocked: `false`
   - legacy_interview_cta_status: `deleted`
   - CTA lead-in verified: `打开智能柜周经营复盘工具页，在浏览器本地完成本周复盘：`

4. **公众号欢迎语 + 关键词「复盘表」**
   - piece_id: `o1-wechat-autoreply-fupan`
   - packet: `data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json`
   - external_status: `configured` (enabled)
   - employment_boundary_synced: `true`
   - false Excel download claim: **no**

## Schedule / ledger

- Approved organic-only schedule: `data/growth/organic-only-schedule-2026-08-15.json` (approved=True)
- Experiment ledger overlay: `data/growth/organic-experiment-ledger-2026-08-15.json`
- Manifest: `data/growth/organic-sprint-phase1-manifest-2026-08-15.json`
- Anti-duplication: same WeChat OA 14d core-question overlap → `same_channel_topic_overlap_with_2026-08-15_article`
- Rule: draft ≠ scheduled/published; `deleted` only for `legacy_interview_cta_status`

## Continue / Stop

- Continue · `organic_pieces_on_dates`: 2026-08-15 公众号文章《点位有销量却不赚钱？用一张周表算清单点贡献》完成 Agy 同步后人工发布；2026-08-17 缺货贴图计划保持 canceled；2026-08-18 知乎改写《库存显示有货，为什么柜机还是缺货？》按计划人工发布
- Continue · `same_channel_14d_core_question_dedupe`: 同一公众号 14 天内核心问题高度相似内容禁止再发布；冲突时取消后续计划并标注 same_channel_topic_overlap_with_2026-08-15_article
- Continue · `single_cta_compliance`: 每条内容仅一个周复盘工具页行动入口（或引导回复「复盘表」），且带本条追踪参数；无访谈 CTA
- Continue · `self_serve_funnel_only`: 公开内容 → 关注公众号 → 回复「复盘表」→ 自助使用周经营复盘工具；可公开订阅，无一对一/加微信/访谈
- Continue · `professional_boundaries`: 不使用现任公司内部经营数据、客户名单、未公开案例、内部流程截图、同事观点；不以雇主名义发言；示例仅用公开资料、合成数据或匿名通用场景。
- Continue · `no_private_distribution`: 未使用朋友圈、微信群/社群、个人号私发或私域群发
- Continue · `autoreply_no_excel_claim`: 欢迎语与关键词「复盘表」均未声称可下载表格文件
- Continue · `solo_hours`: 连续两周实际投入 ≤15 小时/周
- Stop · `private_channel_used`: 立即停止该分发动作并回滚口径；本冲刺仅保留公众号与知乎公开面
- Stop · `interview_or_one_to_one_cta`: 停止发布该稿；改为自助「复盘表」/工具页 CTA
- Stop · `employer_boundary_breach`: 下架或改正文案；删除内部数据/客户/未公开案例/同事观点痕迹
- Stop · `second_cta_or_raw_url_visible_on_wechat`: 停止发布该稿；修正为中文可见文案 + 隐藏链接参数
- Stop · `excel_download_false_claim`: 停止自动回复上线；改为指向浏览器周复盘工具
- Stop · `fabricated_read_lift`: 渠道报表仍过期时，停止宣称阅读已提升

## Browser handoff

1. (wechat_oa_backend) 公众号欢迎语与关键词「复盘表」已 configured/enabled；employment_boundary_synced=true。不得用 deleted 描述自动回复规则。
2. (wechat_oa_image_post) 微信贴图《柜机缺货先查这7步》发布计划已 canceled；原因 same_channel_topic_overlap_with_2026-08-15_article；草稿仍为 draft_saved（5 图顺序完整与 provenance 保留）；scheduled=false；published=false；不删除外部草稿或素材文件；employment_boundary_synced=true。历史 admin_qr_verification_required 仍记录为已安全退出的定时尝试，不再作为活跃发布计划。不得用 deleted 描述贴图草稿。
3. (wechat_oa_article_revision) 《点位有销量却不赚钱？用一张周表算清单点贡献》本地状态为 production_ready_revision / external_sync_pending；供 Agy 浏览器同步既有草稿；不得标已同步/已发布/已定时；不得操作公众号后台发表。
4. (zhihu_editor) Agy 新账号已核验知乎草稿 2072013992894149965：文末为「打开智能柜周经营复盘工具页，在浏览器本地完成本周复盘：」；原唯一锚文本与 UTM 不变；访谈/人工跟进/加微信/一对一联系/身份征集均为 0；platform_draft_state=draft；draft_saved；revision_pending=false；employment_boundary_synced=true；publish_blocked=false；scheduled=false；published=false。历史临时配额阻塞（antigravity_quota_temporarily_exhausted）已 resolved；legacy_interview_cta_status=deleted（仅表示旧访谈文案已删，不表示草稿本身被删）。
5. (ledger) 已回写 organic-only 排期与实验台账：WeChat autoreply configured/enabled；贴图计划 canceled（same_channel_topic_overlap_with_2026-08-15_article）；草稿/5 图/provenance 保留为 draft_saved；单点贡献稿 production_ready_revision / external_sync_pending；Zhihu draft_saved / publish_blocked=false / employment_boundary_synced=true；legacy_interview_cta_status=deleted；历史 antigravity_quota_temporarily_exhausted 已 resolved；草稿≠scheduled/published。

## Antigravity

- Bitmap images: **images_ready**（缺货贴图 5 张保留；发布计划 canceled）
- Cursor prepared revision + briefs only; do not generate bitmaps here.
- Point-contribution: Agy browser sync only; no WeChat backend publish.
