"""Prepare Content Launch 01 draft assets. Never auto-approves."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.company_audit import audit_company, prioritize_review_queue, rows_as_dicts
from research.relations import build_relation_index
from scripts.export_public_bundle import _load_catalog

CATALOG = Path("data/research/public-catalog.json")
METRIC_DISCLAIMER = (
    "不同企业在数据口径、统计周期、终端定义和业务场景上可能存在差异，"
    "实际使用时应结合自身业务口径。"
)

SOURCES = [
    {
        "id": "src-ubox-home",
        "url": "https://www.ubox.cn/",
        "title": "友宝在线官网",
        "source_name": "友宝在线",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
    {
        "id": "src-feng1-home",
        "url": "https://www.feng1.com/zh-CN",
        "title": "丰e足食官网",
        "source_name": "丰e足食",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
    {
        "id": "src-cloudpick-cases",
        "url": "https://www.cloudpick.com/case-studies/case-studies-all",
        "title": "云拿科技案例库",
        "source_name": "云拿科技",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
    {
        "id": "src-cloudpick-suzhou",
        "url": "https://www.cloudpick.com/company/news/company-info/data_119.html",
        "title": "云拿案例文章：苏州交投能源",
        "source_name": "云拿科技",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
    {
        "id": "src-hetun-home",
        "url": "https://www.hetunai.cn/",
        "title": "合豚科技官网",
        "source_name": "合豚科技",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
    {
        "id": "src-hibianli-home",
        "url": "https://www.hibianli.cn/",
        "title": "嗨便利官网",
        "source_name": "嗨便利",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
    {
        "id": "src-inhand-product",
        "url": "https://www.inhand.com.cn/products/ai-vending-machines/",
        "title": "映翰通 AI 智能售货柜产品页",
        "source_name": "映翰通",
        "credibility": "high",
        "source_type": "official",
        "published_at": None,
        "accessed_at": "2026-08-02",
    },
]

CASES = [
    {
        "id": "case-cloudpick-suzhou-energy",
        "slug": "cloudpick-suzhou-energy-ai-store",
        "title": "苏州交投能源 AI 无人店（公开案例）",
        "problem": "交通能源场景需要延长服务时间、降低人工值守成本。",
        "solution": "引入 AI 无人店方案。",
        "how_it_works": "云拿官网披露该项目于 2020 年引入无人店，并公开了员工使用与开店后的经营描述。",
        "public_results": ["公开资料未披露可核验的量化结果。"],
        "limitations": [
            "公开材料偏项目介绍，缺少可复核的经营指标时间序列",
            "场景与商品结构不可直接外推到办公楼智能柜",
        ],
        "company_ids": [],
        "status": "draft",
    },
    {
        "id": "case-cloudpick-shanghai-business-school",
        "slug": "cloudpick-shanghai-business-school",
        "title": "上海商学院无人零售项目（公开案例）",
        "problem": "校园场景需要补充就餐与零售便利性。",
        "solution": "AI 无人店作为“第二食堂”式补充。",
        "how_it_works": "云拿案例库将项目描述为丰富师生就餐选择，并兼具实践基地用途。",
        "public_results": ["公开资料未披露可核验的量化结果。"],
        "limitations": ["案例描述偏定性", "校园场景规则与办公楼不同"],
        "company_ids": [],
        "status": "draft",
    },
    {
        "id": "case-cloudpick-leiyunshang",
        "slug": "cloudpick-leiyunshang-pharmacy",
        "title": "雷允上 AI 无人药店（公开案例）",
        "problem": "医药零售需要延长服务时段并控制值守成本。",
        "solution": "24 小时 AI 无人药店。",
        "how_it_works": "云拿案例库公开列出雷允上 AI 无人药店，覆盖非处方药与健康日用品。",
        "public_results": ["公开资料未披露可核验的量化结果。"],
        "limitations": ["医药合规要求高，不可简单复制到普通智能柜", "缺量化结果"],
        "company_ids": [],
        "status": "draft",
    },
]

CASE_NOTES = {
    "cloudpick-suzhou-energy-ai-store": {
        "公开事实": "云拿官网案例文章披露项目引入与经营描述。",
        "ZeroRealm推断": "交通能源场景可能对 24 小时可达性更敏感。",
        "ZeroRealm观点": "适合作为 AI 无人店公开证据样本，不宜直接当作智能柜通用标杆。",
        "缺失资料": "缺可核验 GMV/客流/损耗数据。",
        "人工审核事项": "核对原文链接是否仍可访问，摘录是否过度解读。",
        "source": {
            "label": "云拿案例文章",
            "url": "https://www.cloudpick.com/company/news/company-info/data_119.html",
        },
    },
    "cloudpick-shanghai-business-school": {
        "公开事实": "云拿案例库公开列出该校园项目定位。",
        "ZeroRealm推断": "教育场景可能同时承担教学演示功能。",
        "ZeroRealm观点": "可作为校园无人零售公开样本，不宜夸大商业回报。",
        "缺失资料": "缺人流、客单、损耗等核验数据。",
        "人工审核事项": "确认案例库条目与项目名称一致。",
        "source": {
            "label": "云拿科技案例库",
            "url": "https://www.cloudpick.com/case-studies/case-studies-all",
        },
    },
    "cloudpick-leiyunshang-pharmacy": {
        "公开事实": "案例库公开列出雷允上 AI 无人药店品类范围。",
        "ZeroRealm推断": "非处方药场景对识别准确率与售后流程要求更高。",
        "ZeroRealm观点": "是垂直场景证据，不是通用智能柜效率证明。",
        "缺失资料": "缺差错率、客诉、监管合规材料。",
        "人工审核事项": "区分营销表述与可核验事实。",
        "source": {
            "label": "云拿科技案例库",
            "url": "https://www.cloudpick.com/case-studies/case-studies-all",
        },
    },
}

SIGNALS = [
    {
        "id": "sig-ubox-platform-scope",
        "slug": "ubox-platform-scope-public",
        "title": "友宝公开披露多形态智能零售终端与平台服务",
        "summary": "友宝在线官网披露其运营多种智能零售终端，并提供设备销售、代运营、商品采销与广告服务。",
        "why_it_matters": "说明头部运营商已从单设备走向平台化能力组合。",
        "affected_roles": ["operators", "brands"],
        "judgment": "值得持续跟踪其设备结构与场景分布的公开披露，而非推测市占率。",
        "claim_ids": [],
        "source_ids": ["src-ubox-home"],
        "company_ids": [],
        "verification_status": "reviewing",
        "published_at": "",
        "tags": ["operator", "smart_retail"],
    },
    {
        "id": "sig-feng1-office-focus",
        "slug": "feng1-office-unmanned-positioning",
        "title": "丰e足食公开定位办公室小场景无人零售",
        "summary": "丰e足食官网将其定位为办公室小场景无人零售运营商，并披露智能柜、自动贩卖机及直营服务能力。",
        "why_it_matters": "办公楼场景是智能柜高频讨论场景，公开定位有助于对照运营模型。",
        "affected_roles": ["operators"],
        "judgment": "应优先核验其场景定义与服务边界，避免把直营模型当成通用加盟模型。",
        "claim_ids": [],
        "source_ids": ["src-feng1-home"],
        "company_ids": [],
        "verification_status": "reviewing",
        "published_at": "",
        "tags": ["office", "smart_cabinet"],
    },
    {
        "id": "sig-cloudpick-case-library",
        "slug": "cloudpick-public-case-library",
        "title": "云拿公开案例库展示无人店与无人仓落地",
        "summary": "云拿科技官网公开展示无人店和无人仓方案，以及多个国内外落地案例。",
        "why_it_matters": "为 AI 视觉零售提供可引用的公开项目清单。",
        "affected_roles": ["hardware", "operators"],
        "judgment": "案例库适合做证据入口，量化结论仍需逐案核验。",
        "claim_ids": [],
        "source_ids": ["src-cloudpick-cases"],
        "company_ids": [],
        "verification_status": "reviewing",
        "published_at": "",
        "tags": ["ai_vision", "case"],
    },
    {
        "id": "sig-hetun-stack",
        "slug": "hetun-integrated-stack",
        "title": "合豚公开披露视觉识别到运营后台的一体化能力",
        "summary": "合豚科技官网披露从视觉识别、硬件、支付、IoT 到运营后台的一体化能力。",
        "why_it_matters": "反映软硬件一体供应商的产品叙事方式。",
        "affected_roles": ["hardware", "software"],
        "judgment": "需区分能力清单与可核验交付边界。",
        "claim_ids": [],
        "source_ids": ["src-hetun-home"],
        "company_ids": [],
        "verification_status": "reviewing",
        "published_at": "",
        "tags": ["saas", "vision"],
    },
    {
        "id": "sig-hibianli-dynamic-vision",
        "slug": "hibianli-dynamic-vision-cabinet",
        "title": "嗨便利公开展示动态视觉智能售货柜",
        "summary": "嗨便利官网展示动态视觉识别智能售货柜及其适用场景。",
        "why_it_matters": "动态视觉柜是智能柜技术路线之一，公开产品页可作对照。",
        "affected_roles": ["hardware", "operators"],
        "judgment": "产品展示不等于统一识别准确率结论。",
        "claim_ids": [],
        "source_ids": ["src-hibianli-home"],
        "company_ids": [],
        "verification_status": "reviewing",
        "published_at": "",
        "tags": ["smart_cabinet"],
    },
    {
        "id": "sig-inhand-grab-go",
        "slug": "inhand-grab-go-cabinet",
        "title": "映翰通公开 Grab & Go 智能售货柜与运营平台",
        "summary": "映翰通产品页披露 Grab & Go 智能售货柜及库存、销售数据运营能力。",
        "why_it_matters": "边缘视觉路线在公开材料中可被定位。",
        "affected_roles": ["hardware"],
        "judgment": "应以其产品页陈述为边界，避免外推市场份额。",
        "claim_ids": [],
        "source_ids": ["src-inhand-product"],
        "company_ids": [],
        "verification_status": "reviewing",
        "published_at": "",
        "tags": ["edge_vision"],
    },
]


def upsert_by_id(items: list[dict], new_items: list[dict]) -> list[dict]:
    by_id = {item["id"]: item for item in items}
    for item in new_items:
        by_id[item["id"]] = item
    return list(by_id.values())


def enrich_metrics(catalog: dict) -> list[dict]:
    related = {
        "terminal-gmv": ["stockout-rate", "sku-sell-through-rate", "gross-margin"],
        "stockout-rate": ["replenish-ontime-rate", "lane-availability", "sku-sell-through-rate"],
        "offline-rate": ["device-online-rate"],
        "device-online-rate": ["offline-rate"],
        "sku-sell-through-rate": ["stockout-rate", "inventory-turnover"],
        "replenish-ontime-rate": ["stockout-rate", "inventory-accuracy"],
        "inventory-turnover": ["inventory-accuracy", "sku-sell-through-rate"],
        "inventory-accuracy": ["inventory-turnover", "shrinkage-rate"],
        "shrinkage-rate": ["inventory-accuracy", "complaint-rate"],
        "gross-margin": ["terminal-gmv", "order-success-rate"],
        "order-success-rate": ["complaint-rate", "device-online-rate"],
        "complaint-rate": ["order-success-rate", "shrinkage-rate"],
        "repurchase-rate": ["terminal-gmv", "sku-sell-through-rate"],
        "lane-availability": ["stockout-rate", "replenish-ontime-rate"],
        "site-survival-rate": ["terminal-gmv", "gross-margin"],
    }
    why = {
        "terminal-gmv": "衡量单点产出，是选址与运营是否划算的基础尺子。",
        "stockout-rate": "缺货直接损失成交，也放大补货与选品问题。",
        "offline-rate": "离线意味着交易与库存同步中断，影响履约与对账。",
        "device-online-rate": "在线率是运维健康度的首要观察指标。",
        "sku-sell-through-rate": "识别无效库存与滞销，指导汰换。",
        "replenish-ontime-rate": "连接缺货与运力，衡量履约承诺。",
        "inventory-turnover": "资金占用与动销效率的综合观察。",
        "inventory-accuracy": "账实不符会误导补货与财务。",
        "shrinkage-rate": "损耗影响毛利，也提示识别/防损问题。",
        "gross-margin": "收入质量指标，需与损耗、履约成本同看。",
        "order-success-rate": "交易完成能力，影响用户信任。",
        "complaint-rate": "体验与售后压力的早期信号。",
        "repurchase-rate": "点位粘性与商品匹配度的代理指标。",
        "lane-availability": "货道可用是成交机会的物理上限。",
        "site-survival-rate": "点位是否可持续，避免只看短期 GMV。",
    }
    briefs = []
    for metric in catalog.get("metrics", []):
        slug = metric["slug"]
        briefs.append(
            {
                "id": metric["id"],
                "slug": slug,
                "name": metric["name"],
                "definition": metric["definition"],
                "whyItMatters": why.get(slug, "用于终端经营诊断与跨点位比较。"),
                "formula": metric.get("formula", ""),
                "variableNotes": "公式变量需在企业内统一定义统计周期、终端集合与订单范围。",
                "applicableScenarios": metric.get("applicable_scenarios", []),
                "commonPitfalls": metric.get("common_pitfalls", []),
                "口径差异": METRIC_DISCLAIMER,
                "relatedMetricSlugs": related.get(slug, []),
                "misleadingWhen": "在口径未对齐时做跨企业排名或对外宣传。",
                "relatedTopics": ["终端运营", "补货履约", "设备运维"],
                "relatedCases": [],
                "status": metric.get("status", "draft"),
            }
        )
    return briefs


def write_company_review_packages(queue: list[dict]) -> None:
    root = Path("dist/review/company")
    for row in queue:
        package = root / row["slug"]
        package.mkdir(parents=True, exist_ok=True)
        risks = "\n".join(f"- {item}" for item in (row.get("risks") or [])) or "- —"
        missing = ", ".join(row.get("missing_fields") or []) or "—"
        md = f"""# 企业审核包：{row['name']}

- slug: `{row['slug']}`
- status: `{row['status']}`（不得自动批准）
- readiness: `{row['readiness']}`
- coreBusiness: {row.get('core_business') or '—'}

## 【公开事实】

当前 catalog 摘要：{row.get('summary') or '—'}

需人工从官网/年报/监管披露中补齐可核验事实。

## 【ZeroRealm 推断】

基于角色标签 `{row.get('core_business')}` 的研究优先级推断，不构成事实认定。

## 【ZeroRealm 观点】

首批应优先核验智能柜核心玩家；在无高可信来源前保持 draft。

## 【缺失资料】

{missing}

## 【人工审核事项】

- 补充 official/high 来源 URL
- 重写 summary（去掉“公开图谱收录”模板）
- 填写 verifiedAt
- 明确不得自动 approved

## Risks

{risks}
"""
        (package / "review.md").write_text(md, encoding="utf-8")


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["sources"] = upsert_by_id(catalog.get("sources") or [], SOURCES)
    catalog["cases"] = upsert_by_id(catalog.get("cases") or [], CASES)
    catalog["signals"] = upsert_by_id(catalog.get("signals") or [], SIGNALS)
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    briefs = enrich_metrics(catalog)
    Path("data/research").mkdir(parents=True, exist_ok=True)
    Path("data/research/metric-briefs.json").write_text(
        json.dumps(
            {"disclaimer": METRIC_DISCLAIMER, "autoApproved": False, "metrics": briefs},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    Path("data/research/case-review-notes.json").write_text(
        json.dumps({"autoApproved": False, "notes": CASE_NOTES}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    loaded = _load_catalog(CATALOG)
    rows = [audit_company(c) for c in loaded.companies.values() if c.status == "draft"]
    queue = prioritize_review_queue(rows, limit=10)
    Path("data/research/review-queue-companies.json").write_text(
        json.dumps(
            {
                "generatedFor": "human-review-only",
                "autoApproved": False,
                "items": rows_as_dicts(queue),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_company_review_packages(rows_as_dicts(queue))
    Path("dist").mkdir(parents=True, exist_ok=True)
    Path("dist/content-network-index.json").write_text(
        json.dumps(build_relation_index(loaded), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "metrics": len(briefs),
                "cases": len(CASES),
                "signals": len(SIGNALS),
                "queue": len(queue),
                "autoApproved": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
