"""Build-time relation index across research entities (no database)."""

from __future__ import annotations

from collections import defaultdict

from research.exporters.public_bundle import ResearchCatalog


def build_relation_index(catalog: ResearchCatalog) -> dict:
    company_to = defaultdict(lambda: {"signals": [], "cases": [], "topics": [], "metrics": []})
    signal_to = defaultdict(lambda: {"companies": [], "claims": [], "topics": []})
    case_to = defaultdict(lambda: {"companies": [], "topics": [], "metrics": []})
    topic_to = defaultdict(
        lambda: {"companies": [], "cases": [], "signals": [], "metrics": []}
    )
    metric_to = defaultdict(lambda: {"cases": [], "topics": []})

    for signal in catalog.signals.values():
        for company_id in signal.company_ids:
            company_to[company_id]["signals"].append(signal.id)
            signal_to[signal.id]["companies"].append(company_id)
        signal_to[signal.id]["claims"] = list(signal.claim_ids)

    for case in catalog.cases.values():
        for company_id in case.company_ids:
            company_to[company_id]["cases"].append(case.id)
            case_to[case.id]["companies"].append(company_id)

    for topic in catalog.topics.values():
        for company_id in topic.company_ids:
            company_to[company_id]["topics"].append(topic.id)
            topic_to[topic.id]["companies"].append(company_id)
        for case_id in topic.case_ids:
            case_to[case_id]["topics"].append(topic.id)
            topic_to[topic.id]["cases"].append(case_id)
        for signal_id in topic.signal_ids:
            signal_to[signal_id]["topics"].append(topic.id)
            topic_to[topic.id]["signals"].append(signal_id)
        for metric_id in topic.metric_ids:
            metric_to[metric_id]["topics"].append(topic.id)
            topic_to[topic.id]["metrics"].append(metric_id)

    for metric in catalog.metrics.values():
        for case_id in metric.related_case_ids:
            metric_to[metric.id]["cases"].append(case_id)
            case_to[case_id]["metrics"].append(metric.id)

    return {
        "companies": {key: dict(value) for key, value in company_to.items()},
        "signals": {key: dict(value) for key, value in signal_to.items()},
        "cases": {key: dict(value) for key, value in case_to.items()},
        "topics": {key: dict(value) for key, value in topic_to.items()},
        "metrics": {key: dict(value) for key, value in metric_to.items()},
    }
