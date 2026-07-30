# ZeroRealm Data

零售行业数据采集、知识处理和日报生成系统 —— ZeroRealm AI 的数据引擎。

## Quick Start

```bash
git clone https://github.com/zerorealm/zerorealm-data.git
cd zerorealm-data
pip install -r requirements.txt
python main.py --source 36kr_rss
```

## 输出目录

```text
data/raw/       ← 原始 JSON
data/clean/     ← 清洗后 Markdown
data/digest/    ← 每日日报素材
```

## CLI

```bash
python main.py                                      # 采集全部已启用源
python main.py --source 36kr_rss                    # 采集一个源
python main.py --source 36kr_rss,ubox_web           # 采集指定源集合
python main.py --date 2026-08-01 --source 36kr_rss  # 指定输出日期
python main.py --debug                              # 详细日志
```

## 运行范围

完整白名单维护在 `config/sources.yaml`。每日 Workflow 暂时只运行 5 个核心源，
先完成连续稳定性验证，再逐步扩大范围。

## 架构

```text
Scheduler (GitHub Actions)
    → Crawler (RSS / HTML)
    → Parser
    → Cleaner + Dedup
    → Writer (JSON / Markdown)
    → Digest
    → AI Daily Report (MDX)
    → Website content/daily
```

## 自动化

`.github/workflows/daily-crawl.yaml` 每天北京时间 06:00：

1. 运行测试；
2. 采集 5 个核心源；
3. 生成日报 MDX；
4. 将数据、日志和日报保存为 Workflow Artifact；
5. 同步日报到官网仓库。

跨仓库同步需要在数据仓库配置 `WEBSITE_REPO_TOKEN` Secret。该 Fine-grained
PAT 只需授予 `LoganWang123/zerorealm-website` 的 Contents read/write 权限。

## 验证

```bash
python -m pytest -q
ruff check .
```

## 关联文档

- [Data Strategy V1.1](../公司规划/数据采集/Data%20Strategy%20V1.0.md)
- [M1 Data Demo Plan V1.2](../公司规划/数据采集/M1%20Data%20Demo%20Plan.md)
- [TDD — Data Crawler V1.2](../公司规划/数据采集/TDD.md) 
