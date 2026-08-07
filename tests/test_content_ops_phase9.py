"""Phase 9–11 content ops: audit/lint never mutate; no Agnes in packages."""

from __future__ import annotations

import json
from pathlib import Path

from research.company_audit import audit_company, prioritize_review_queue, readiness
from research.content_lint import lint_company, lint_metric
from research.models import CompanyProfile, MetricDefinition
from scripts.export_content_package import export_package
from scripts.export_industry_map_dataset import export_dataset
from scripts.export_public_bundle import _load_catalog


def test_lint_and_audit_do_not_change_status():
    company = CompanyProfile(
        id="co-x",
        slug="demo-co",
        name="示例",
        summary="公开图谱收录的企业",
        core_business="operator",
        status="draft",
    )
    before = company.status
    lint_company(company)
    row = audit_company(company)
    assert company.status == before == "draft"
    assert row.readiness == "NOT_READY"


def test_metric_lint_requires_pitfalls():
    metric = MetricDefinition(
        id="m1",
        slug="x",
        name="x",
        definition="定义",
        common_pitfalls=[],
        status="approved",
    )
    issues = lint_metric(metric)
    assert any(item.code == "METRIC_MISSING_PITFALLS" for item in issues)


def test_review_queue_not_auto_approved():
    catalog = _load_catalog(Path("data/research/public-catalog.json"))
    rows = [audit_company(c) for c in catalog.companies.values() if c.status == "draft"]
    queue = prioritize_review_queue(rows, limit=10)
    assert 1 <= len(queue) <= 10
    assert all(item.status == "draft" for item in queue)


def test_content_package_has_no_agnes_and_pending_media(tmp_path):
    package = export_package(
        slug="demo-pack",
        title="测试包",
        body="正文",
        out_root=tmp_path,
    )
    meta = json.loads((package / "metadata.json").read_text(encoding="utf-8"))
    assert meta["agnesImageGeneration"] is False
    assert (package / "media" / "pending").exists() or meta["media"]["assets"]


def test_industry_map_dataset_draft_marked_review_only(tmp_path):
    out = tmp_path / "map-dir"
    report = export_dataset(
        Path("data/research/public-catalog.json"),
        out,
        include_draft=True,
    )
    payload = json.loads((out / "review-status.json").read_text(encoding="utf-8"))
    assert report["visibility"] == "FOR_REVIEW_ONLY"
    assert payload["visibility"] == "FOR_REVIEW_ONLY"
    assert payload["autoApproved"] is False


def test_readiness_ready_requires_sources_and_approval():
    company = CompanyProfile(
        id="co-y",
        slug="ready-co",
        name="示例就绪",
        summary="经过公开来源整理的运营摘要",
        core_business="operator",
        scenarios=["办公楼"],
        verified_at="2026-08-01",
        status="approved",
    )
    # Without high sources still NEEDS_REVIEW
    assert readiness(company, sources=[]) == "NEEDS_REVIEW"
