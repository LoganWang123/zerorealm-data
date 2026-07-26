# ZeroRealm Data

零售行业数据采集系统 —— ZeroRealm AI 的数据引擎。

## Quick Start

```bash
git clone https://github.com/zerorealm/zerorealm-data.git
cd zerorealm-data
pip install -r requirements.txt
python main.py
```

## 输出目录

```text
data/raw/       ← 原始 JSON
data/clean/     ← 清洗后 Markdown
data/digest/    ← 每日日报素材
```

## CLI

```bash
python main.py                    # 采集所有源
python main.py --source 36kr_rss  # 只采集指定源
python main.py --debug            # 详细日志
```

## 数据源

| ID | 名称 | 类型 | 状态 |
| --- | --- | --- | --- |
| 36kr_rss | 36氪 | RSS | ✅ |
| ubox_web | 友宝官网 | Web | ✅ |
| linkshop_web | 联商网 | Web | ✅ |

## 架构

```text
Scheduler (GitHub Actions)
    → Crawler (RSS / HTML)
    → Parser
    → Cleaner + Dedup
    → Writer (JSON / Markdown)
    → Digest
```

## 关联文档

- [Data Strategy V1.1](../公司规划/数据采集/Data%20Strategy%20V1.0.md)
- [M1 Data Demo Plan V1.2](../公司规划/数据采集/M1%20Data%20Demo%20Plan.md)
- [TDD — Data Crawler V1.2](../公司规划/数据采集/TDD.md)
