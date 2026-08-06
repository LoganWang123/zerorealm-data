"""Export an approved research catalog to Public Content Bundle v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.exporters.public_bundle import ResearchCatalog, export_public_bundle
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


def _load_catalog(path: Path) -> ResearchCatalog:
    raw = json.loads(path.read_text(encoding="utf-8"))

    sources = {
        item["id"]: SourceDocument(
            id=item["id"],
            url=item.get("url", ""),
            title=item.get("title", ""),
            source_name=item.get("source_name", item.get("sourceName", "")),
            published_at=item.get("published_at", item.get("publishedAt")),
            fetched_at=item.get("fetched_at", item.get("fetchedAt", "")),
            raw_excerpt=item.get("raw_excerpt", item.get("rawExcerpt", "")),
            credibility=item.get("credibility", "medium"),
        )
        for item in raw.get("sources", [])
    }
    claims = {
        item["id"]: Claim(
            id=item["id"],
            text=item["text"],
            type=ClaimType(item["type"]),
            status=ClaimStatus(item.get("status", "draft")),
            confidence=Confidence(item.get("confidence", "medium")),
            source_ids=list(item.get("source_ids", item.get("sourceIds", []))),
            evidence_ids=list(item.get("evidence_ids", item.get("evidenceIds", []))),
            based_on_claim_ids=list(
                item.get("based_on_claim_ids", item.get("basedOnClaimIds", []))
            ),
            reviewed_at=item.get("reviewed_at", item.get("reviewedAt")),
            review_note=item.get("review_note", item.get("reviewNote", "")),
        )
        for item in raw.get("claims", [])
    }
    signals = {
        item["id"]: IndustrySignal(
            id=item["id"],
            slug=item["slug"],
            title=item["title"],
            summary=item.get("summary", ""),
            why_it_matters=item.get("why_it_matters", item.get("whyItMatters", "")),
            affected_roles=list(
                item.get("affected_roles", item.get("affectedRoles", []))
            ),
            judgment=item.get("judgment", ""),
            claim_ids=list(item.get("claim_ids", item.get("claimIds", []))),
            source_ids=list(item.get("source_ids", item.get("sourceIds", []))),
            verification_status=item.get(
                "verification_status", item.get("verificationStatus", "draft")
            ),
            company_ids=list(item.get("company_ids", item.get("companyIds", []))),
            published_at=item.get("published_at", item.get("publishedAt", "")),
            tags=list(item.get("tags", [])),
        )
        for item in raw.get("signals", [])
    }
    companies = {
        item["id"]: CompanyProfile(
            id=item["id"],
            slug=item["slug"],
            name=item["name"],
            summary=item.get("summary", ""),
            core_business=item.get("core_business", item.get("coreBusiness", "")),
            products=list(item.get("products", [])),
            scenarios=list(item.get("scenarios", [])),
            business_model=item.get("business_model", item.get("businessModel", "")),
            related_case_ids=list(
                item.get("related_case_ids", item.get("relatedCaseIds", []))
            ),
            related_signal_ids=list(
                item.get("related_signal_ids", item.get("relatedSignalIds", []))
            ),
            verified_at=item.get("verified_at", item.get("verifiedAt", "")),
            status=item.get("status", "draft"),
        )
        for item in raw.get("companies", [])
    }
    cases = {
        item["id"]: CaseStudy(
            id=item["id"],
            slug=item["slug"],
            title=item["title"],
            problem=item.get("problem", ""),
            solution=item.get("solution", ""),
            how_it_works=item.get("how_it_works", item.get("howItWorks", "")),
            public_results=list(
                item.get("public_results", item.get("publicResults", []))
            ),
            evidence_ids=list(item.get("evidence_ids", item.get("evidenceIds", []))),
            limitations=list(item.get("limitations", [])),
            company_ids=list(item.get("company_ids", item.get("companyIds", []))),
            status=item.get("status", "draft"),
        )
        for item in raw.get("cases", [])
    }
    metrics = {
        item["id"]: MetricDefinition(
            id=item["id"],
            slug=item["slug"],
            name=item["name"],
            definition=item.get("definition", ""),
            formula=item.get("formula", ""),
            applicable_scenarios=list(
                item.get("applicable_scenarios", item.get("applicableScenarios", []))
            ),
            common_pitfalls=list(
                item.get("common_pitfalls", item.get("commonPitfalls", []))
            ),
            related_case_ids=list(
                item.get("related_case_ids", item.get("relatedCaseIds", []))
            ),
            status=item.get("status", "draft"),
        )
        for item in raw.get("metrics", [])
    }
    topics = {
        item["id"]: Topic(
            id=item["id"],
            slug=item["slug"],
            title=item["title"],
            summary=item.get("summary", ""),
            signal_ids=list(item.get("signal_ids", item.get("signalIds", []))),
            company_ids=list(item.get("company_ids", item.get("companyIds", []))),
            case_ids=list(item.get("case_ids", item.get("caseIds", []))),
            metric_ids=list(item.get("metric_ids", item.get("metricIds", []))),
            status=item.get("status", "draft"),
        )
        for item in raw.get("topics", [])
    }
    return ResearchCatalog(
        sources=sources,
        claims=claims,
        signals=signals,
        companies=companies,
        cases=cases,
        metrics=metrics,
        topics=topics,
        content_revision=int(raw.get("contentRevision", raw.get("content_revision", 1))),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="Research catalog JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/public-v1"),
        help="Output bundle directory",
    )
    parser.add_argument(
        "--generated-at",
        required=True,
        help="ISO-8601 timestamp written into manifest.generatedAt",
    )
    args = parser.parse_args()
    catalog = _load_catalog(args.catalog)
    manifest = export_public_bundle(
        catalog,
        args.output,
        generated_at=args.generated_at,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
