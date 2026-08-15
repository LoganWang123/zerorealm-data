# Organic sprint phase 1 packets · 2026-08-15

- Status: `phase1_external_ops_recorded`
- Image status: `images_ready`
- External API mutation (repo): `False`
- Browser manual ops: `True`
- LLM API: `False`
- Friends circle / groups / private: forbidden
- Secrets policy: no CDN URLs / login tokens / cookies recorded
- Conversion: `公开内容 → 关注公众号 → 回复「复盘表」→ 自助使用周经营复盘工具；可公开订阅，无一对一/加微信/访谈`
- Professional boundaries: declared in packet compliance

## Packets

1. **WeChat 贴图** `2026-08-17` 《柜机缺货先查这7步》
   - piece_id: `o1-wechat-stockout-tieku`
   - tracking: `organic_20260817_wechat_tieku_stockout7`
   - packet: `data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json`
   - image briefs: 5（1:1 方封面 + 4×4:5 竖屏合步：1-2 / 3-4 / 5-6 / 7）
   - assets: `assets/generated/organic-sprint/2026-08-15/o1-wechat-stockout-tieku/`（cover + panel-1..4）
   - image_status: `images_ready`
   - CTA: 关注公众号后回复「复盘表」，自助打开智能柜周经营复盘工具；可在工具页公开订阅经营清单

2. **Zhihu 场景改写** `2026-08-18` 《库存显示有货，为什么柜机还是缺货？》
   - piece_id: `o1-zhihu-inventory-stockout`
   - tracking: `organic_20260818_zhihu_inventory_stockout`
   - packet: `data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json`
   - CTA: 关注公众号后回复「复盘表」，自助打开智能柜周经营复盘工具；可在工具页公开订阅经营清单

3. **公众号欢迎语 + 关键词「复盘表」**
   - piece_id: `o1-wechat-autoreply-fupan`
   - packet: `data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json`
   - false Excel download claim: **no**
   - interview CTA: **removed**

## Schedule / ledger

- Approved organic-only schedule: `data/growth/organic-only-schedule-2026-08-15.json` (approved=True)
- Experiment ledger overlay: `data/growth/organic-experiment-ledger-2026-08-15.json`
- Manifest: `data/growth/organic-sprint-phase1-manifest-2026-08-15.json`

## Anonymous 14d metrics

- `content_prep_on_time_rate`: 计划内容按期准备率（草稿/配置就绪人工核对；未观测不填造）
- `keyword_replies`: 关键词「复盘表」回复数（公众号后台人工计数；未观测保持 0）
- `tool_views`: 工具页访问（网站 tool_view / 人工录入；未观测保持 0）
- `public_platform_engagement_delta`: 公开平台收藏/赞同/阅读变化（仅渠道报表新鲜时录入，否则保持 null，不虚构）

## Continue / Stop

- Continue · `organic_pieces_on_dates`: 2026-08-17 公众号贴图《柜机缺货先查这7步》与 2026-08-18 知乎改写《库存显示有货，为什么柜机还是缺货？》均已人工发布
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

1. (wechat_oa_backend · configured) 已核验：被关注回复与关键词「复盘表」精确匹配均已保存启用；中文富文本链接，无原始网址可见。后续勿用本仓接口改写。
2. (wechat_oa_image_post · blocked) 草稿《柜机缺货先查这7步》已 draft_saved（5 图顺序完整）；定时 2026-08-17T20:30:00+08:00 因 admin_qr_verification_required 阻塞并已安全退出。勿记为 scheduled/published；仅公众号公开面；禁止朋友圈/群/私发。
3. (zhihu_editor · draft_saved) 知乎草稿《库存显示有货，为什么柜机还是缺货？》已 draft_saved；网页端不支持定时；计划窗口 2026-08-18T20:30:00+08:00；未提前发布。
4. (ledger) 已回写 organic-only 排期与实验台账：configured / draft_saved / blocked；草稿≠scheduled/published。

## Antigravity

- Bitmap images: **images_ready**
- Generator / reviewer: Antigravity · model `gemini-3.7-flash-high`
- Provenance: `assets/generated/organic-sprint/2026-08-15/provenance.json`
- Cursor only rewrites paths / hashes / status; does not generate bitmaps.
