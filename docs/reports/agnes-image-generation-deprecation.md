# Agnes Image Generation Deprecation

日期：2026-08-07

## 决策

Agnes 图片生成质量不符合 ZeroRealm 要求。**生产路径彻底停止 Agnes 生图。**
禁止任何 Agnes image fallback。

## 当前生产入口（已切断）

| 入口 | 原行为 | 现状 |
|------|--------|------|
| `PublishWorkflow._build_media_service` | 构造 `AgnesClient` | 仅 `LocalImageGenerator`；拒绝 `provider=agnes` |
| `GenerateMediaStep` | 捕获 `AgnesAPIError` | 捕获 local/pending/disabled 错误 |
| `generate_media.py homepage` | 调 Agnes | 直接 `AGNES_IMAGE_GENERATION_DISABLED` |
| `homepage.client_from_environment` | 读 `AGNES_API_KEY` | 抛出 disabled |
| `daily-crawl.yaml` | 注入 `AGNES_*` | 已移除；可选 `ZEROREALM_LOCAL_IMAGE_CMD` |

## 测试入口（历史兼容）

- `tests/test_agnes_client.py` — 直测 deprecated client（不代表生产会调用）
- `tests/test_media_generation.py` — `FakeAgnesClient` 测编排复用逻辑
- `tests/test_local_media_policy.py` — **断言生产路径 Agnes 调用次数为 0**

## 配置

- `config/publish.yaml` → `media.provider: local`
- `MediaConfig.provider` 默认 `local`
- `.env.example` 标注 AGNES_* deprecated

## Secret

- `AGNES_API_KEY` 不再由 CI 注入用于生图
- 本地 `.env` 若仍含该键：忽略即可；建议轮换后删除

## Fallback

**已删除。** local unavailable → `dist/media-jobs/` prompt package → `pending_local_generation`。

## 文档

- README 已改为本地媒体生成说明
- 旧 superpowers 计划/规格仍可能提及 Agnes，视为历史文档

## 软废弃原则

- 保留 `AgnesClient` 源码与历史测试，避免高风险大删除
- 构造时发出 `DeprecationWarning`
- 生产工厂路径永不返回 live Agnes client
