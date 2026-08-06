from pathlib import Path

from scripts.bootstrap_research_assets import bootstrap_catalog
from knowledge.foundation_graph import FOUNDATION_GRAPH_PATH


def test_bootstrap_keeps_companies_draft_and_metrics_approved():
    catalog = bootstrap_catalog(FOUNDATION_GRAPH_PATH)
    assert catalog["bootstrap"]["companyCount"] >= 10
    assert catalog["bootstrap"]["metricCount"] == 15
    assert all(company["status"] == "draft" for company in catalog["companies"])
    assert all(metric["status"] == "approved" for metric in catalog["metrics"])
    assert Path(FOUNDATION_GRAPH_PATH).exists()
