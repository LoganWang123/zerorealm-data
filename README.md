# ZeroRealm Data

零售行业数据采集、知识处理、内容生成与渠道发布系统 —— ZeroRealm AI 的研究与内容生产后端。

仓库地址：`https://github.com/LoganWang123/zerorealm-data`

## Quick Start

```bash
git clone https://github.com/LoganWang123/zerorealm-data.git
cd zerorealm-data
pip install -r requirements.txt
python main.py --source 36kr_rss
```

## 输出目录

```text
data/raw/       ← 原始 JSON
data/clean/     ← 清洗后 Markdown
data/digest/    ← 每日日报素材
output_daily/   ← 生成的日报 MDX（本地，默认不入库）
dist/public-v1/ ← Public Content Bundle（后续阶段导出）
```

## CLI

```bash
python main.py                                      # 采集全部已启用源
python main.py --source 36kr_rss                    # 采集一个源
python main.py --source 36kr_rss,ubox_web           # 采集指定源集合
python main.py --date 2026-08-01 --source 36kr_rss  # 指定输出日期
python main.py --debug                              # 详细日志

python generate_daily.py --date 2026-08-06          # 生成日报 MDX
python run_daily.py --date 2026-08-06               # 采集 + 生成 + 本地复制到网站目录（默认不 push）
python run_daily.py --date 2026-08-06 --push-website  # 显式启用本地 git push 网站仓库
```

## 运行范围

完整白名单维护在 `config/sources.yaml`。每日 Workflow 暂时只运行核心启用源，
先完成连续稳定性验证，再逐步扩大范围。

## 架构

```text
Scheduler (GitHub Actions)
    → Crawler (RSS / HTML / JS / API)
    → Dedup + Quality
    → Writer (JSON / Markdown) + Digest
    → AI Daily Report (MDX)
    → Media generate/validate (optional)
    → Sync MDX + media to zerorealm-website (Actions)
    → Verified WeChat draft (no auto mass-send)
```

研究领域模型（`research/`）与 Public Bundle 契约正在渐进接入；现有
`Article` + `PublishWorkflow` 继续作为微信等渠道的发布交换层。详见
[ADR 0001](docs/adr/0001-research-public-bundle.md)。

## 自动化

`.github/workflows/daily-crawl.yaml` 每天 **北京时间 23:00**
（cron：`0 15 * * *` UTC）：

1. 运行测试；
2. 采集已启用源；
3. 生成日报 MDX；
4. 生成并校验公众号配图（dry-run 发布管线）；
5. 在配置了 `WEBSITE_REPO_TOKEN` 时，将日报 MDX 与配图同步到
   `LoganWang123/zerorealm-website` 并 push（触发 Vercel）；
6. 校验生产页与图片可访问后，创建或更新微信草稿；
7. 将数据、日志、日报与素材保存为 Workflow Artifact。

### 官网同步状态

| 路径 | 状态 |
|------|------|
| GitHub Actions + `WEBSITE_REPO_TOKEN` | **推荐的唯一自动同步入口**（当前已实现 daily MDX + media） |
| 本地 `run_daily.py` | 默认只采集/生成/复制到本地网站目录；**不 push** |
| 本地 `run_daily.py --push-website` | 显式启用本地 git push（过渡期逃生舱，待 Actions 稳定后移除） |

跨仓库同步需要在数据仓库配置 `WEBSITE_REPO_TOKEN` Secret。该 Fine-grained
PAT 只需授予 `LoganWang123/zerorealm-website` 的 Contents read/write 权限。

## 本地媒体生成（Agnes 生图已停用）

**Agnes 不再用于任何图片生成。** 生产默认 `media.provider=local`。
无本地模型时写入 `dist/media-jobs/` prompt package（`pending_local_generation`），
**不会** fallback 到 Agnes。

```bash
python scripts/generate_local_media.py <content-id> --channel wechat --purpose cover
python scripts/generate_local_media.py <content-id> --prompt-only
```

可选本机命令（不设则用程序化品牌模板）：

```text
ZEROREALM_LOCAL_IMAGE_CMD
```

公众号素材仍须人工审核（SHA 绑定）：

```bash
python review_media.py --date YYYY-MM-DD \
  --approve cover=<SHA256> \
  --approve body_1=<SHA256> \
  --approve body_2=<SHA256> \
  --approve body_3=<SHA256>
```

`generate_media.py homepage` 与 `AGNES_API_KEY` 仅保留为历史兼容/文档说明，
生产路径会拒绝 Agnes 生图。详见
`docs/reports/agnes-image-generation-deprecation.md`。

最终图片、视频和 `homepage-media.json` 写入官网的 `public/media/home/`。
密钥只允许通过环境变量提供，不应写入仓库或日志。

## 验证

```bash
python -m pytest -q
ruff check .
```

## 关联文档

- [ADR 0001 — Research + Public Bundle](docs/adr/0001-research-public-bundle.md)
- [Data Strategy V1.1](../公司规划/数据采集/Data%20Strategy%20V1.0.md)
- [M1 Data Demo Plan V1.2](../公司规划/数据采集/M1%20Data%20Demo%20Plan.md)
- [TDD — Data Crawler V1.2](../公司规划/数据采集/TDD.md)
