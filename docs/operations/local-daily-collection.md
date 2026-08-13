# 双保险无 LLM 每日采集

本文档已迁至 [local-collection.md](./local-collection.md)。

政策摘要：云端 cron（北京 23:00）保连续；本机 launchd 开机补充；两边仅 `--local-only` 采集，无 LLM / 发布。云端 `collect` 不依赖契约测试、不装 Playwright 浏览器；采集健康门以「至少一个启用源成功」为通过线。
