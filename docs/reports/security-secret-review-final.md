# Security Secret Review — Final

日期：2026-08-07  
规则：不打印任何 Secret 值。

## 复核对象

| 路径 | 分类 | 说明 |
|------|------|------|
| `docs/superpowers/plans/2026-07-29-agnes-media-pipeline.md` | **D 无法确认** | 文档中的 key 赋值形态；长度较短。需人工打开确认。若为真实密钥：轮换 Agnes（即使已停用生图）并避免再扩散。 |
| `tests/test_agnes_client.py` | **A 测试假值** | 夹具字符串用于脱敏断言。 |
| `.env.example` | **B 示例值** | 占位符；Agnes 已标 deprecated。 |

## 当前状态

- HEAD 生产路径不注入 / 不调用 Agnes 生图
- 本地 `.env` 仍可能含疑似真实密钥（未跟踪）→ **建议轮换**
- 不做 history rewrite，不 push

## 需要人工轮换的服务商（若确认泄露）

- Agnes（历史）
- 以及本地 `.env` 中出现的其他 API（LLM / WeChat 等）——仅在确认真实后轮换
