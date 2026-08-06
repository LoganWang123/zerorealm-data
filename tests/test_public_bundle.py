"""Public Bundle v1 export contracts and safety gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.exporters.public_bundle import (
    PublicBundleError,
    ResearchCatalog,
    export_public_bundle,
)
from research.models import (
    CaseStudy,
    Claim,
    ClaimStatus,
    ClaimType,
    CompanyProfile,
    Confidence,
    IndustrySignal,
    MetricDefinition,
    SourceDocument,
    Topic,
)
from research.serialization import (
    FORBIDDEN_PUBLIC_KEYS,
    serialize_claim,
    serialize_company,
    serialize_source,
)


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts" / "public-v1"


def _source(**overrides) -> SourceDocument:
    data = dict(
        id="src-1",
        url="https://example.com/news/1",
        title="公开新闻",
        source_name="Example",
        published_at="2026-08-06",
        fetched_at="internal/path/raw.json",
        raw_excerpt="内部原文不应导出",
        credibility="high",
    )
    data.update(overrides)
    return SourceDocument(**data)


def _fact(**overrides) -> Claim:
    data = dict(
        id="cl-1",
        text="运营商宣布扩大投放",
        type=ClaimType.FACT,
        status=ClaimStatus.VERIFIED,
        confidence=Confidence.HIGH,
        source_ids=["src-1"],
        evidence_ids=["ev-secret"],
        reviewed_at="2026-08-06T12:00:00+08:00",
        review_note="内部审核备注",
    )
    data.update(overrides)
    return Claim(**data)


def _company(**overrides) -> CompanyProfile:
    data = dict(
        id="co-1",
        slug="feng-e",
        name="丰e足食",
        summary="智能零售运营商",
        core_business="智能柜运营",
        products=["智能柜"],
        scenarios=["办公楼"],
        business_model="投放+零售",
        related_case_ids=["case-1"],
        related_signal_ids=["sig-1"],
        verified_at="2026-08-06",
        status="approved",
    )
    data.update(overrides)
    return CompanyProfile(**data)


def _case(**overrides) -> CaseStudy:
    data = dict(
        id="case-1",
        slug="office-replenish",
        title="办公楼补货优化",
        problem="缺货率高",
        solution="按动销补货",
        how_it_works="日更补货单",
        public_results=["缺货率下降"],
        evidence_ids=["ev-secret"],
        limitations=["不适配冷启动"],
        company_ids=["co-1"],
        status="published",
    )
    data.update(overrides)
    return CaseStudy(**data)


def _metric(**overrides) -> MetricDefinition:
    data = dict(
        id="metric-1",
        slug="stockout-rate",
        name="缺货率",
        definition="缺货次数/应售次数",
        formula="stockouts/expected",
        applicable_scenarios=["智能柜"],
        common_pitfalls=["忽略临时下架"],
        related_case_ids=["case-1"],
        status="approved",
    )
    data.update(overrides)
    return MetricDefinition(**data)


def _signal(**overrides) -> IndustrySignal:
    data = dict(
        id="sig-1",
        slug="expand-2026-08-06",
        title="投放扩大",
        summary="运营商扩大办公楼投放",
        why_it_matters="影响点位模型",
        affected_roles=["operators"],
        judgment="值得跟踪",
        claim_ids=["cl-1"],
        source_ids=["src-1"],
        verification_status="verified",
        company_ids=["co-1"],
        published_at="2026-08-06",
        tags=["smart_cabinet"],
    )
    data.update(overrides)
    return IndustrySignal(**data)


def _topic(**overrides) -> Topic:
    data = dict(
        id="topic-1",
        slug="replenishment",
        title="补货效率",
        summary="补货专题",
        signal_ids=["sig-1"],
        company_ids=["co-1"],
        case_ids=["case-1"],
        metric_ids=["metric-1"],
        status="approved",
    )
    data.update(overrides)
    return Topic(**data)


def _catalog(**overrides) -> ResearchCatalog:
    data = dict(
        sources={"src-1": _source()},
        claims={"cl-1": _fact()},
        signals={"sig-1": _signal()},
        companies={"co-1": _company()},
        cases={"case-1": _case()},
        metrics={"metric-1": _metric()},
        topics={"topic-1": _topic()},
        content_revision=1,
    )
    data.update(overrides)
    return ResearchCatalog(**data)


def test_serialization_uses_whitelist_and_strips_sensitive_fields():
    claim = serialize_claim(_fact())
    source = serialize_source(_source())
    company = serialize_company(_company())

    assert set(claim) <= {
        "id",
        "text",
        "type",
        "confidence",
        "sourceIds",
        "basedOnClaimIds",
    }
    assert "reviewNote" not in claim
    assert "review_note" not in claim
    assert "evidenceIds" not in claim
    assert set(source) <= {
        "id",
        "url",
        "title",
        "sourceName",
        "publishedAt",
        "credibility",
    }
    assert "rawExcerpt" not in source
    assert "fetchedAt" not in source
    assert "prompt" not in company
    assert FORBIDDEN_PUBLIC_KEYS & set(claim) == set()


def test_draft_claim_and_unapproved_entities_are_not_exported(tmp_path):
    catalog = _catalog(
        claims={
            "cl-1": _fact(),
            "cl-draft": _fact(
                id="cl-draft",
                text="未审核事实",
                status=ClaimStatus.DRAFT,
            ),
        },
        companies={
            "co-1": _company(),
            "co-draft": _company(id="co-draft", slug="draft-co", status="draft"),
        },
    )
    manifest = export_public_bundle(
        catalog,
        tmp_path / "public-v1",
        generated_at="2026-08-06T23:00:00+08:00",
    )
    claims = json.loads((tmp_path / "public-v1" / "claims.json").read_text(encoding="utf-8"))
    companies = list((tmp_path / "public-v1" / "companies").glob("*.json"))
    assert [c["id"] for c in claims] == ["cl-1"]
    assert [path.name for path in companies] == ["feng-e.json"]
    assert manifest["counts"]["claims"] == 1
    assert manifest["counts"]["companies"] == 1


def test_export_rejects_fact_without_source_and_broken_refs():
    catalog = _catalog(
        claims={"cl-1": _fact(source_ids=[])},
    )
    with pytest.raises(PublicBundleError, match="FACT_MISSING_SOURCE"):
        export_public_bundle(
            catalog,
            Path("unused"),
            generated_at="2026-08-06T23:00:00+08:00",
        )

    broken = _catalog(signals={"sig-1": _signal(company_ids=["missing-co"])})
    with pytest.raises(PublicBundleError, match="BROKEN_REFERENCE"):
        export_public_bundle(
            broken,
            Path("unused"),
            generated_at="2026-08-06T23:00:00+08:00",
        )


def test_export_writes_expected_layout_and_passes_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    from referencing import Registry, Resource

    out = tmp_path / "public-v1"
    manifest = export_public_bundle(
        _catalog(),
        out,
        generated_at="2026-08-06T23:00:00+08:00",
    )

    assert (out / "manifest.json").exists()
    assert (out / "signals.json").exists()
    assert (out / "claims.json").exists()
    assert (out / "sources.json").exists()
    assert (out / "content-index.json").exists()
    assert (out / "companies" / "feng-e.json").exists()
    assert (out / "cases" / "office-replenish.json").exists()
    assert (out / "metrics" / "stockout-rate.json").exists()
    assert (out / "topics" / "replenishment.json").exists()
    assert not (out / "articles").exists()

    registry = Registry()
    for path in CONTRACTS.glob("*.schema.json"):
        contents = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(
            contents["$id"],
            Resource.from_contents(contents),
        )

    schema_map = {
        "manifest.json": "manifest.schema.json",
        "signals.json": "signals.schema.json",
        "claims.json": "claims.schema.json",
        "sources.json": "sources.schema.json",
        "content-index.json": "content-index.schema.json",
        "companies/feng-e.json": "company.schema.json",
        "cases/office-replenish.json": "case.schema.json",
        "metrics/stockout-rate.json": "metric.schema.json",
        "topics/replenishment.json": "topic.schema.json",
    }
    for rel, schema_name in schema_map.items():
        payload = json.loads((out / rel).read_text(encoding="utf-8"))
        schema = json.loads((CONTRACTS / schema_name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, registry=registry).validate(payload)

    assert manifest["contractVersion"] == "1.0"
    assert manifest["counts"]["signals"] == 1
    assert "bundleHash" in manifest
    assert "files" in manifest


def test_export_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    export_public_bundle(_catalog(), a, generated_at="2026-08-06T23:00:00+08:00")
    export_public_bundle(_catalog(), b, generated_at="2026-08-06T23:00:00+08:00")

    files_a = sorted(p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes()


def test_export_is_atomic_on_failure(tmp_path):
    out = tmp_path / "public-v1"
    out.mkdir()
    marker = out / "keep-me.txt"
    marker.write_text("old", encoding="utf-8")
    (out / "signals.json").write_text("[]\n", encoding="utf-8")

    with pytest.raises(PublicBundleError):
        export_public_bundle(
            _catalog(claims={"cl-1": _fact(source_ids=[])}),
            out,
            generated_at="2026-08-06T23:00:00+08:00",
        )

    assert marker.read_text(encoding="utf-8") == "old"
    assert (out / "signals.json").read_text(encoding="utf-8") == "[]\n"
    assert not (out / "manifest.json").exists()


def test_exported_json_never_contains_sensitive_keys_or_internal_payload(tmp_path):
    out = tmp_path / "public-v1"
    export_public_bundle(_catalog(), out, generated_at="2026-08-06T23:00:00+08:00")
    blob = "\n".join(path.read_text(encoding="utf-8") for path in out.rglob("*.json"))
    for key in (
        "reviewNote",
        "review_note",
        "rawExcerpt",
        "raw_excerpt",
        "fetchedAt",
        "evidenceIds",
        "prompt",
        "modelResponse",
        "apiKey",
        "secret",
        "artifactPath",
    ):
        assert key not in blob
    assert "内部审核备注" not in blob
    assert "内部原文不应导出" not in blob
    assert "internal/path/raw.json" not in blob
    assert "ev-secret" not in blob


def test_industry_signal_to_public_dict_stays_compatible():
    signal = _signal()
    from research.serialization import serialize_signal

    assert signal.to_public_dict() == serialize_signal(signal)
