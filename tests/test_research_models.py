"""Tests for research domain models and claim validation."""

from __future__ import annotations

from research.intake import news_to_research_atoms
from research.models import (
    CaseStudy,
    Claim,
    ClaimStatus,
    ClaimType,
    CompanyProfile,
    Confidence,
    Evidence,
    IndustrySignal,
    MetricDefinition,
    ResearchBrief,
    SourceDocument,
    Topic,
)
from research.validators import ValidationIssue, validate_claim, validate_claims


def test_source_evidence_claim_roundtrip_fields():
    source = SourceDocument(
        id="src-1",
        url="https://example.com/news/1",
        title="某智能柜运营商宣布新一轮补货策略",
        source_name="Example News",
        published_at="2026-08-06",
    )
    evidence = Evidence(
        id="ev-1",
        source_id=source.id,
        quote="运营商将试点按动销率补货",
    )
    claim = Claim(
        id="cl-1",
        text="该运营商将试点按动销率补货",
        type=ClaimType.FACT,
        status=ClaimStatus.VERIFIED,
        confidence=Confidence.HIGH,
        source_ids=[source.id],
        evidence_ids=[evidence.id],
        reviewed_at="2026-08-06T12:00:00+08:00",
        review_note="核对原文",
    )

    assert source.url.startswith("https://")
    assert evidence.source_id == "src-1"
    assert claim.type is ClaimType.FACT
    assert claim.status is ClaimStatus.VERIFIED


def test_industry_signal_public_dict_matches_bundle_shape():
    signal = IndustrySignal(
        id="sig-1",
        slug="smart-cabinet-replenish-2026-08-06",
        title="智能柜补货策略出现动销导向试点",
        summary="运营商宣布按动销率试点补货",
        why_it_matters="直接影响缺货率与周转",
        affected_roles=["operators", "brands"],
        judgment="值得本周跟踪补货时效指标",
        claim_ids=["cl-1"],
        source_ids=["src-1"],
        verification_status="verified",
        company_ids=["co-1"],
        published_at="2026-08-06",
        tags=["smart_cabinet", "ops"],
    )

    payload = signal.to_public_dict()
    assert payload == {
        "id": "sig-1",
        "slug": "smart-cabinet-replenish-2026-08-06",
        "title": "智能柜补货策略出现动销导向试点",
        "summary": "运营商宣布按动销率试点补货",
            "whyItMatters": "直接影响缺货率与周转",
        "affectedRoles": ["brands", "operators"],
        "judgment": "值得本周跟踪补货时效指标",
        "claimIds": ["cl-1"],
        "sourceIds": ["src-1"],
        "companyIds": ["co-1"],
        "verificationStatus": "verified",
        "publishedAt": "2026-08-06",
        "tags": ["ops", "smart_cabinet"],
    }


def test_company_case_metric_topic_and_brief_exist():
    company = CompanyProfile(
        id="co-1",
        slug="feng-e",
        name="丰e足食",
        summary="智能零售运营商",
        core_business="智能柜运营",
        products=["智能柜"],
        scenarios=["办公楼"],
        business_model="设备投放+商品零售",
        verified_at="2026-08-06",
    )
    case = CaseStudy(
        id="case-1",
        slug="office-replenish",
        title="办公楼补货时效优化",
        problem="缺货率偏高",
        solution="按动销补货",
        how_it_works="日更动销榜驱动补货单",
        public_results=["缺货率下降"],
        evidence_ids=["ev-1"],
        limitations=["不适用于新品冷启动"],
    )
    metric = MetricDefinition(
        id="metric-1",
        slug="stockout-rate",
        name="缺货率",
        definition="缺货 SKU 次数 / 应售 SKU 次数",
        formula="stockouts / expected_sku_slots",
        applicable_scenarios=["智能柜运营"],
        common_pitfalls=["忽略临时下架"],
        related_case_ids=["case-1"],
    )
    topic = Topic(
        id="topic-1",
        slug="replenishment",
        title="补货效率",
        summary="围绕补货时效与动销的专题",
        signal_ids=["sig-1"],
        company_ids=["co-1"],
        case_ids=["case-1"],
        metric_ids=["metric-1"],
    )
    brief = ResearchBrief(
        id="brief-1",
        slug="weekly-replenish",
        title="本周补货观察",
        summary="动销导向补货值得跟踪",
        signal_ids=["sig-1"],
        claim_ids=["cl-1"],
        company_ids=["co-1"],
        case_ids=["case-1"],
        metric_ids=["metric-1"],
        topic_ids=["topic-1"],
    )

    assert company.name == "丰e足食"
    assert case.limitations
    assert metric.slug == "stockout-rate"
    assert topic.signal_ids == ["sig-1"]
    assert brief.status == "draft"


def test_news_item_converts_to_source_fact_inference_opinion():
    atoms = news_to_research_atoms(
        {
            "title": "丰e足食扩大办公楼智能柜投放",
            "url": "https://example.com/feng-e-expand",
            "source_name": "36氪",
            "published_at": "2026-08-06",
            "excerpt": "公司宣布将在华东办公楼场景扩大智能柜投放。",
            "insight": "办公楼密度提升可能改善单点模型。",
            "opinion": "运营商应同步观察补货半径，而不是只看柜量。",
        }
    )

    assert isinstance(atoms.source, SourceDocument)
    assert atoms.source.url == "https://example.com/feng-e-expand"
    assert len(atoms.claims) == 3
    assert [c.type for c in atoms.claims] == [
        ClaimType.FACT,
        ClaimType.INFERENCE,
        ClaimType.OPINION,
    ]
    assert atoms.claims[0].source_ids == [atoms.source.id]
    assert atoms.claims[1].based_on_claim_ids == [atoms.claims[0].id]
    assert atoms.evidence[0].source_id == atoms.source.id


def test_validate_claim_blocks_unverified_fact_without_source():
    claim = Claim(
        id="cl-bad",
        text="某公司融资一亿元",
        type=ClaimType.FACT,
        status=ClaimStatus.DRAFT,
        confidence=Confidence.HIGH,
        source_ids=[],
    )
    issues = validate_claim(claim, sources={})
    codes = {issue.code for issue in issues}
    assert "FACT_MISSING_SOURCE" in codes
    assert "FACT_NOT_VERIFIED" in codes
    assert any(issue.severity == "error" for issue in issues)


def test_validate_claim_requires_inference_to_cite_facts():
    inference = Claim(
        id="cl-inf",
        text="这会改善单柜模型",
        type=ClaimType.INFERENCE,
        status=ClaimStatus.DRAFT,
        confidence=Confidence.MEDIUM,
        source_ids=["src-1"],
        based_on_claim_ids=[],
    )
    issues = validate_claim(
        inference,
        sources={
            "src-1": SourceDocument(
                id="src-1",
                url="https://example.com/a",
                title="a",
                source_name="Example",
                published_at="2026-08-06",
            )
        },
        claims={},
    )
    assert any(issue.code == "INFERENCE_MISSING_FACT_BASIS" for issue in issues)


def test_validate_claim_warns_when_opinion_reads_like_fact():
    opinion = Claim(
        id="cl-op",
        text="该公司必将成为行业第一",
        type=ClaimType.OPINION,
        status=ClaimStatus.DRAFT,
        confidence=Confidence.LOW,
        source_ids=["src-1"],
    )
    issues = validate_claim(
        opinion,
        sources={
            "src-1": SourceDocument(
                id="src-1",
                url="https://example.com/a",
                title="a",
                source_name="Example",
                published_at=None,
            )
        },
    )
    codes = {issue.code for issue in issues}
    assert "OPINION_AS_FACT" in codes
    assert "SOURCE_MISSING_PUBLISHED_AT" in codes


def test_validate_claims_blocks_missing_source_url():
    source = SourceDocument(
        id="src-1",
        url="",
        title="无链接稿件",
        source_name="Unknown",
        published_at="2026-08-06",
    )
    claim = Claim(
        id="cl-1",
        text="发生了某事",
        type=ClaimType.FACT,
        status=ClaimStatus.VERIFIED,
        confidence=Confidence.HIGH,
        source_ids=["src-1"],
        reviewed_at="2026-08-06T12:00:00+08:00",
    )
    issues = validate_claims([claim], sources={"src-1": source})
    assert any(issue.code == "SOURCE_MISSING_URL" for issue in issues)


def test_validation_issue_structure():
    issue = ValidationIssue(
        code="FACT_MISSING_SOURCE",
        message="fact requires source",
        severity="error",
        claim_id="cl-1",
    )
    assert issue.severity == "error"
