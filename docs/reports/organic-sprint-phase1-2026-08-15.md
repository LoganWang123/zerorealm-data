# Organic sprint phase 1 packets · 2026-08-15

- Status: `phase1_packets_ready`
- Image status: `awaiting_antigravity_images`
- External mutation: `False`
- LLM API: `False`
- Friends circle / groups / private: forbidden

## Packets

1. **WeChat 贴图** `2026-08-17` 《柜机缺货先查这7步》
   - piece_id: `o1-wechat-stockout-tieku`
   - tracking: `organic_20260817_wechat_tieku_stockout7`
   - packet: `data/growth/content-packet-o1-wechat-stockout-tieku-2026-08-15.json`
   - image briefs: 5（1:1 方封面 + 4×4:5 竖屏合步：1-2 / 3-4 / 5-6 / 7）

2. **Zhihu 场景改写** `2026-08-18` 《库存显示有货，为什么柜机还是缺货？》
   - piece_id: `o1-zhihu-inventory-stockout`
   - tracking: `organic_20260818_zhihu_inventory_stockout`
   - packet: `data/growth/content-packet-o1-zhihu-inventory-stockout-2026-08-15.json`

3. **公众号欢迎语 + 关键词「复盘表」**
   - piece_id: `o1-wechat-autoreply-fupan`
   - packet: `data/growth/config-packet-o1-wechat-autoreply-2026-08-15.json`
   - false Excel download claim: **no**

## Schedule / ledger

- Approved organic-only schedule: `data/growth/organic-only-schedule-2026-08-15.json` (approved=True)
- Experiment ledger overlay: `data/growth/organic-experiment-ledger-2026-08-15.json`

## Continue / Stop

- Continue · `organic_pieces_on_dates`: 2026-08-17 公众号贴图《柜机缺货先查这7步》与 2026-08-18 知乎改写《库存显示有货，为什么柜机还是缺货？》均已人工发布
- Continue · `single_cta_compliance`: 每条内容仅一个周复盘工具页行动入口，且带本条追踪参数
- Continue · `no_private_distribution`: 未使用朋友圈、微信群/社群、个人号私发或私域群发
- Continue · `autoreply_no_excel_claim`: 欢迎语与关键词「复盘表」均未声称可下载表格文件
- Continue · `solo_hours`: 连续两周实际投入 ≤15 小时/周
- Stop · `private_channel_used`: 立即停止该分发动作并回滚口径；本冲刺仅保留公众号与知乎公开面
- Stop · `second_cta_or_raw_url_visible_on_wechat`: 停止发布该稿；修正为中文可见文案 + 隐藏链接参数
- Stop · `excel_download_false_claim`: 停止自动回复上线；改为指向浏览器周复盘工具
- Stop · `fabricated_read_lift`: 渠道报表仍过期时，停止宣称阅读已提升

## Browser handoff

1. (wechat_oa_backend) 浏览器打开公众号后台 → 自动回复：粘贴欢迎语与关键词「复盘表」配置包；链接用后台超链接/菜单，勿把完整网址写成可见纯文本；保存后自测关注与关键词，勿调用本仓发布接口。
2. (wechat_oa_image_post) 待 Antigravity 贴图位图就绪后，于 2026-08-17 人工发布《柜机缺货先查这7步》；仅公众号公开面；禁止朋友圈/群/私发。
3. (zhihu_editor) 于 2026-08-18 在知乎编辑器粘贴场景改写稿；文末仅保留一个指向周复盘工具的中文锚点链接；人工发布。
4. (ledger) 发布日记入 organic-only 排期与实验台账：是否单行动入口、是否禁用私域分发、图片状态。

## Antigravity

- Bitmap images: **awaiting_antigravity_images**
- Cursor prepared image briefs only; do not generate bitmaps in this phase.
