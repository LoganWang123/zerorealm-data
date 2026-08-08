# Security Secret Review (Phase 8)

日期：2026-08-07  
规则：**不打印任何 Secret 值。**

## 复核对象

| 路径 | Commit | 分类 | 说明 |
|------|--------|------|------|
| `docs/superpowers/plans/2026-07-29-agnes-media-pipeline.md` | `7f602a14d58f…` | **D 无法判断** | 文档中存在 `AGNES_API_KEY` 赋值形态；长度较短，不能自动认定真伪。建议人工打开确认；若为真实密钥则轮换并从历史清理。 |
| `tests/test_agnes_client.py` | `94ad46c3ae1e…` | **A 明确假值** | 测试夹具字符串（如 `secret-agnes-key` / `test-key` 风格），用于异常脱敏断言。 |
| `.env.example` | `d4aed1cce450…` | **B 示例** | 占位符模板；已标注 Agnes deprecated。 |

## 未跟踪本地文件

| 路径 | 分类 | 动作 |
|------|------|------|
| `zerorealm-data/.env` | **C 疑似真实**（未进 Git） | 轮换其中全部密钥；确认 gitignore |
| `zerorealm-website/.env.local` | 视内容 | 保持 gitignore；勿提交 |

## 结论

- Git 跟踪文件中 **无已确认的 D→必须立即 rewrite 的泄露**（文档项保持人工复核）。
- Agnes 生图生产路径已停用，降低 `AGNES_API_KEY` 被 CI/日志误用的风险。
