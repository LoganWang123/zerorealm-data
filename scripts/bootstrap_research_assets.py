"""Bootstrap draft research assets from public foundation graph and metric dictionary.

Does not invent commercial facts. Company profiles stay draft unless already approved.
Metric definitions are generic industry definitions and may be marked approved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from knowledge.foundation_graph import FOUNDATION_GRAPH_PATH, load_foundation_nodes

GENERIC_METRICS = [
    {
        "slug": "terminal-gmv",
        "name": "单终端 GMV",
        "definition": "统计周期内单个零售终端产生的商品成交额。",
        "formula": "sum(order_gmv) / active_terminals",
        "scenarios": ["智能柜", "无人货架", "便利店"],
        "pitfalls": ["口径需明确是否含税、退货与测试订单"],
    },
    {
        "slug": "stockout-rate",
        "name": "缺货率",
        "definition": "应售 SKU/货道中处于缺货状态的比例。",
        "formula": "stockout_slots / expected_slots",
        "scenarios": ["智能柜补货", "即时零售履约"],
        "pitfalls": ["临时下架与真实缺货需区分"],
    },
    {
        "slug": "offline-rate",
        "name": "离线率",
        "definition": "统计周期内设备处于离线状态的时长占比。",
        "formula": "offline_seconds / observed_seconds",
        "scenarios": ["智能柜运维", "设备监控"],
        "pitfalls": ["短时重连抖动可能高估离线"],
    },
    {
        "slug": "device-online-rate",
        "name": "设备在线率",
        "definition": "在线设备数占应监控设备数的比例。",
        "formula": "online_devices / managed_devices",
        "scenarios": ["智能柜运维"],
        "pitfalls": ["报废设备未移出资产池会压低指标"],
    },
    {
        "slug": "sku-sell-through-rate",
        "name": "SKU 动销率",
        "definition": "有销量的 SKU 数占总在售 SKU 数的比例。",
        "formula": "skus_with_sales / active_skus",
        "scenarios": ["选品", "补货"],
        "pitfalls": ["新品导入期不宜直接对标成熟 SKU"],
    },
    {
        "slug": "replenish-ontime-rate",
        "name": "补货及时率",
        "definition": "在约定时效内完成的补货任务占比。",
        "formula": "ontime_replenish_tasks / total_replenish_tasks",
        "scenarios": ["智能柜运营"],
        "pitfalls": ["时效定义因城市与点位类型不同"],
    },
    {
        "slug": "inventory-turnover",
        "name": "库存周转",
        "definition": "一定周期内库存被销售替换的次数。",
        "formula": "cogs_or_sales / average_inventory",
        "scenarios": ["智能柜", "便利店"],
        "pitfalls": ["分子用销售额或成本需统一"],
    },
    {
        "slug": "gross-margin",
        "name": "毛利率",
        "definition": "毛利占销售收入的比例。",
        "formula": "(revenue - cogs) / revenue",
        "scenarios": ["经营分析"],
        "pitfalls": ["促销与损耗未计入会高估"],
    },
    {
        "slug": "shrinkage-rate",
        "name": "损耗率",
        "definition": "过期、破损、丢失等损耗占应售成本或货量的比例。",
        "formula": "shrinkage / expected_inventory",
        "scenarios": ["智能柜", "无人零售"],
        "pitfalls": ["需区分自然损耗与异常损耗"],
    },
    {
        "slug": "site-survival-rate",
        "name": "点位存活率",
        "definition": "观察期末仍在运营的点位占期初点位的比例。",
        "formula": "active_sites_end / sites_start",
        "scenarios": ["点位扩张"],
        "pitfalls": ["搬迁与临时闭店需单独标注"],
    },
    {
        "slug": "order-success-rate",
        "name": "订单成功率",
        "definition": "成功完成支付与出货的订单占总发起订单比例。",
        "formula": "successful_orders / initiated_orders",
        "scenarios": ["智能柜交易"],
        "pitfalls": ["用户取消与设备故障应分层统计"],
    },
    {
        "slug": "lane-availability",
        "name": "货道可用率",
        "definition": "可正常售卖货道占总货道比例。",
        "formula": "sellable_lanes / total_lanes",
        "scenarios": ["设备运营"],
        "pitfalls": ["机械卡货与系统锁道都需计入不可用"],
    },
    {
        "slug": "inventory-accuracy",
        "name": "库存准确率",
        "definition": "盘点结果与系统库存一致的比例。",
        "formula": "matched_skus / audited_skus",
        "scenarios": ["补货与审计"],
        "pitfalls": ["抽样盘点不能直接外推全网"],
    },
    {
        "slug": "complaint-rate",
        "name": "客诉率",
        "definition": "客诉次数占订单或活跃用户的比例。",
        "formula": "complaints / orders_or_users",
        "scenarios": ["服务质量"],
        "pitfalls": ["分母选择会显著改变数值"],
    },
    {
        "slug": "repurchase-rate",
        "name": "复购率",
        "definition": "在观察窗口内发生再次购买的用户占比。",
        "formula": "repeat_users / active_users",
        "scenarios": ["用户运营"],
        "pitfalls": ["窗口长度必须固定披露"],
    },
]


def _slug(text: str, prefix: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
    ascii_part = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if ascii_part and len(ascii_part) >= 2 and re.fullmatch(r"[a-z0-9-]+", ascii_part):
        return f"{ascii_part[:40]}"
    return f"{prefix}-{digest}"


def bootstrap_catalog(foundation_path: Path) -> dict:
    nodes = load_foundation_nodes(foundation_path)
    companies = []
    for node in nodes:
        if node.entity_type not in {"company", "brand"}:
            continue
        if node.node_kind != "entity":
            continue
        companies.append(
            {
                "id": f"co-{hashlib.sha256(node.name.encode()).hexdigest()[:12]}",
                "slug": _slug(node.name, "co"),
                "name": node.name,
                "summary": f"{node.name}（公开图谱收录，角色：{node.industry_role or '未标注'}）",
                "core_business": node.industry_role or "",
                "products": [],
                "scenarios": list(node.secondary_layers) or [node.primary_layer],
                "business_model": "",
                "related_case_ids": [],
                "related_signal_ids": [],
                "verified_at": "",
                "status": "draft",
            }
        )

    metrics = []
    for item in GENERIC_METRICS:
        metrics.append(
            {
                "id": f"metric-{item['slug']}",
                "slug": item["slug"],
                "name": item["name"],
                "definition": item["definition"],
                "formula": item["formula"],
                "applicable_scenarios": item["scenarios"],
                "common_pitfalls": item["pitfalls"]
                + ["不同企业口径可能不同，不能当作统一行业标准"],
                "related_case_ids": [],
                "status": "approved",
            }
        )

    topics = [
        {
            "id": "topic-smart-cabinet-ops",
            "slug": "smart-cabinet-ops",
            "title": "智能柜运营",
            "summary": "围绕补货、在线率、点位存活与动销的运营专题。",
            "signal_ids": [],
            "company_ids": [],
            "case_ids": [],
            "metric_ids": [m["id"] for m in metrics[:8]],
            "status": "draft",
        }
    ]

    return {
        "contentRevision": 1,
        "sources": [],
        "claims": [],
        "signals": [],
        "companies": companies,
        "cases": [],
        "metrics": metrics,
        "topics": topics,
        "bootstrap": {
            "note": "Companies/topics remain draft until human review with public sources.",
            "companyCount": len(companies),
            "metricCount": len(metrics),
            "caseCount": 0,
            "signalCount": 0,
            "publishableMetrics": len(metrics),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--foundation",
        type=Path,
        default=FOUNDATION_GRAPH_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "research" / "public-catalog.json",
    )
    args = parser.parse_args()
    catalog = bootstrap_catalog(args.foundation)
    # Strip helper metadata before writing publish catalog
    bootstrap_meta = catalog.pop("bootstrap")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(bootstrap_meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
