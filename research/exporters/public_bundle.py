"""Export approved research assets as Public Content Bundle v1."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from research.models import (
    CaseStudy,
    Claim,
    ClaimStatus,
    ClaimType,
    CompanyProfile,
    IndustrySignal,
    MetricDefinition,
    SourceDocument,
    Topic,
)
from research.serialization import (
    serialize_case,
    serialize_claim,
    serialize_company,
    serialize_metric,
    serialize_signal,
    serialize_source,
    serialize_topic,
)

CONTRACT_VERSION = "1.0"
EXPORTABLE_ENTITY_STATUSES = frozenset({"approved", "published"})
EXPORTABLE_SIGNAL_STATUSES = frozenset({"verified", "approved", "published"})
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACTS_DIR = REPOSITORY_ROOT / "contracts" / "public-v1"


class PublicBundleError(ValueError):
    """Raised when a catalog cannot be exported safely."""


@dataclass
class ResearchCatalog:
    """In-memory research corpus for Public Bundle export."""

    sources: dict[str, SourceDocument] = field(default_factory=dict)
    claims: dict[str, Claim] = field(default_factory=dict)
    signals: dict[str, IndustrySignal] = field(default_factory=dict)
    companies: dict[str, CompanyProfile] = field(default_factory=dict)
    cases: dict[str, CaseStudy] = field(default_factory=dict)
    metrics: dict[str, MetricDefinition] = field(default_factory=dict)
    topics: dict[str, Topic] = field(default_factory=dict)
    content_revision: int = 1


@dataclass
class _SelectedBundle:
    sources: dict[str, SourceDocument]
    claims: dict[str, Claim]
    signals: dict[str, IndustrySignal]
    companies: dict[str, CompanyProfile]
    cases: dict[str, CaseStudy]
    metrics: dict[str, MetricDefinition]
    topics: dict[str, Topic]


def canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _select_exportable(catalog: ResearchCatalog) -> _SelectedBundle:
    claims = {
        claim_id: claim
        for claim_id, claim in catalog.claims.items()
        if claim.status is ClaimStatus.VERIFIED
    }
    signals = {
        signal_id: signal
        for signal_id, signal in catalog.signals.items()
        if signal.verification_status in EXPORTABLE_SIGNAL_STATUSES
    }
    companies = {
        company_id: company
        for company_id, company in catalog.companies.items()
        if company.status in EXPORTABLE_ENTITY_STATUSES
    }
    cases = {
        case_id: case
        for case_id, case in catalog.cases.items()
        if case.status in EXPORTABLE_ENTITY_STATUSES
    }
    metrics = {
        metric_id: metric
        for metric_id, metric in catalog.metrics.items()
        if metric.status in EXPORTABLE_ENTITY_STATUSES
    }
    topics = {
        topic_id: topic
        for topic_id, topic in catalog.topics.items()
        if topic.status in EXPORTABLE_ENTITY_STATUSES
    }

    referenced_source_ids: set[str] = set()
    for claim in claims.values():
        referenced_source_ids.update(claim.source_ids)
    for signal in signals.values():
        referenced_source_ids.update(signal.source_ids)

    sources = {
        source_id: catalog.sources[source_id]
        for source_id in sorted(referenced_source_ids)
        if source_id in catalog.sources
    }
    return _SelectedBundle(
        sources=sources,
        claims=claims,
        signals=signals,
        companies=companies,
        cases=cases,
        metrics=metrics,
        topics=topics,
    )


def _require_ref(
    kind: str,
    ref_id: str,
    available: dict,
    *,
    owner_id: str,
) -> None:
    if ref_id not in available:
        raise PublicBundleError(
            f"BROKEN_REFERENCE: {kind} '{ref_id}' missing for '{owner_id}'"
        )


def validate_selected_bundle(selected: _SelectedBundle) -> None:
    """Enforce publish gates and referential integrity."""
    for claim in selected.claims.values():
        if claim.type is ClaimType.FACT and not claim.source_ids:
            raise PublicBundleError(
                f"FACT_MISSING_SOURCE: claim '{claim.id}' has no sources"
            )
        for source_id in claim.source_ids:
            _require_ref("source", source_id, selected.sources, owner_id=claim.id)
            if not (selected.sources[source_id].url or "").strip():
                raise PublicBundleError(
                    f"SOURCE_MISSING_URL: source '{source_id}' for claim '{claim.id}'"
                )
        for basis_id in claim.based_on_claim_ids:
            _require_ref("claim", basis_id, selected.claims, owner_id=claim.id)

    for signal in selected.signals.values():
        for claim_id in signal.claim_ids:
            _require_ref("claim", claim_id, selected.claims, owner_id=signal.id)
        for source_id in signal.source_ids:
            _require_ref("source", source_id, selected.sources, owner_id=signal.id)
        for company_id in signal.company_ids:
            _require_ref("company", company_id, selected.companies, owner_id=signal.id)

    for company in selected.companies.values():
        for case_id in company.related_case_ids:
            _require_ref("case", case_id, selected.cases, owner_id=company.id)
        for signal_id in company.related_signal_ids:
            _require_ref("signal", signal_id, selected.signals, owner_id=company.id)

    for case in selected.cases.values():
        for company_id in case.company_ids:
            _require_ref("company", company_id, selected.companies, owner_id=case.id)

    for metric in selected.metrics.values():
        for case_id in metric.related_case_ids:
            _require_ref("case", case_id, selected.cases, owner_id=metric.id)

    for topic in selected.topics.values():
        for signal_id in topic.signal_ids:
            _require_ref("signal", signal_id, selected.signals, owner_id=topic.id)
        for company_id in topic.company_ids:
            _require_ref("company", company_id, selected.companies, owner_id=topic.id)
        for case_id in topic.case_ids:
            _require_ref("case", case_id, selected.cases, owner_id=topic.id)
        for metric_id in topic.metric_ids:
            _require_ref("metric", metric_id, selected.metrics, owner_id=topic.id)


def _build_payloads(selected: _SelectedBundle) -> dict[str, object]:
    signals = [
        serialize_signal(selected.signals[key])
        for key in sorted(selected.signals, key=lambda i: selected.signals[i].id)
    ]
    claims = [
        serialize_claim(selected.claims[key])
        for key in sorted(selected.claims, key=lambda i: selected.claims[i].id)
    ]
    sources = [
        serialize_source(selected.sources[key])
        for key in sorted(selected.sources, key=lambda i: selected.sources[i].id)
    ]
    companies = {
        f"companies/{company.slug}.json": serialize_company(company)
        for company in sorted(selected.companies.values(), key=lambda item: item.slug)
    }
    cases = {
        f"cases/{case.slug}.json": serialize_case(case)
        for case in sorted(selected.cases.values(), key=lambda item: item.slug)
    }
    metrics = {
        f"metrics/{metric.slug}.json": serialize_metric(metric)
        for metric in sorted(selected.metrics.values(), key=lambda item: item.slug)
    }
    topics = {
        f"topics/{topic.slug}.json": serialize_topic(topic)
        for topic in sorted(selected.topics.values(), key=lambda item: item.slug)
    }
    content_index = {
        "signals": [
            {"id": item["id"], "slug": item["slug"], "title": item["title"]}
            for item in signals
        ],
        "companies": [
            {"id": payload["id"], "slug": payload["slug"], "title": payload["name"]}
            for _, payload in sorted(companies.items())
        ],
        "cases": [
            {"id": payload["id"], "slug": payload["slug"], "title": payload["title"]}
            for _, payload in sorted(cases.items())
        ],
        "metrics": [
            {"id": payload["id"], "slug": payload["slug"], "title": payload["name"]}
            for _, payload in sorted(metrics.items())
        ],
        "topics": [
            {"id": payload["id"], "slug": payload["slug"], "title": payload["title"]}
            for _, payload in sorted(topics.items())
        ],
        "claims": [{"id": item["id"], "type": item["type"]} for item in claims],
        "sources": [{"id": item["id"], "title": item["title"]} for item in sources],
    }
    payloads: dict[str, object] = {
        "signals.json": signals,
        "claims.json": claims,
        "sources.json": sources,
        "content-index.json": content_index,
    }
    payloads.update(companies)
    payloads.update(cases)
    payloads.update(metrics)
    payloads.update(topics)
    return payloads


def _load_schema_registry(contracts_dir: Path):
    try:
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover
        raise PublicBundleError("referencing is required via jsonschema") from exc

    registry = Registry()
    for path in sorted(contracts_dir.glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(
            contents["$id"],
            Resource.from_contents(contents),
        )
    return registry


def _validate_against_schemas(
    payloads: dict[str, object],
    contracts_dir: Path,
) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency declared in requirements
        raise PublicBundleError("jsonschema is required for Public Bundle export") from exc

    schema_by_file = {
        "signals.json": "signals.schema.json",
        "claims.json": "claims.schema.json",
        "sources.json": "sources.schema.json",
        "content-index.json": "content-index.schema.json",
    }
    single_schemas = {
        "companies/": "company.schema.json",
        "cases/": "case.schema.json",
        "metrics/": "metric.schema.json",
        "topics/": "topic.schema.json",
    }
    cache: dict[str, dict] = {}
    registry = _load_schema_registry(contracts_dir)

    def load_schema(name: str) -> dict:
        if name not in cache:
            path = contracts_dir / name
            cache[name] = json.loads(path.read_text(encoding="utf-8"))
        return cache[name]

    for rel, payload in payloads.items():
        schema_name = schema_by_file.get(rel)
        if schema_name is None:
            for prefix, name in single_schemas.items():
                if rel.startswith(prefix):
                    schema_name = name
                    break
        if schema_name is None:
            continue
        schema = load_schema(schema_name)
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        validator.validate(payload)


def _write_atomic(output_dir: Path, file_texts: dict[str, str]) -> None:
    staging = output_dir.with_name(f"{output_dir.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)

    try:
        for rel, text in file_texts.items():
            path = staging / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

        if output_dir.exists():
            backup = output_dir.with_name(f"{output_dir.name}.bak")
            if backup.exists():
                shutil.rmtree(backup)
            output_dir.rename(backup)
            try:
                staging.rename(output_dir)
            except Exception:
                backup.rename(output_dir)
                raise
            shutil.rmtree(backup)
        else:
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            staging.rename(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def export_public_bundle(
    catalog: ResearchCatalog,
    output_dir: str | Path,
    *,
    generated_at: str,
    contracts_dir: str | Path | None = None,
) -> dict:
    """Validate, serialize, and atomically write a Public Bundle v1 directory."""
    output_path = Path(output_dir)
    contracts_path = Path(contracts_dir) if contracts_dir else DEFAULT_CONTRACTS_DIR

    selected = _select_exportable(catalog)
    validate_selected_bundle(selected)
    payloads = _build_payloads(selected)
    _validate_against_schemas(payloads, contracts_path)

    file_texts = {rel: canonical_json(payload) for rel, payload in payloads.items()}
    files = {rel: _sha256_text(text) for rel, text in sorted(file_texts.items())}
    bundle_hash = _sha256_text(
        canonical_json([{"path": rel, "sha256": digest} for rel, digest in files.items()])
    )
    counts = {
        "signals": len(selected.signals),
        "companies": len(selected.companies),
        "cases": len(selected.cases),
        "metrics": len(selected.metrics),
        "topics": len(selected.topics),
        "claims": len(selected.claims),
        "sources": len(selected.sources),
    }
    manifest = {
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": generated_at,
        "contentRevision": catalog.content_revision,
        "counts": counts,
        "files": files,
        "bundleHash": bundle_hash,
    }
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise PublicBundleError("jsonschema is required for Public Bundle export") from exc
    manifest_schema = json.loads(
        (contracts_path / "manifest.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, manifest_schema)

    file_texts["manifest.json"] = canonical_json(manifest)
    _write_atomic(output_path, file_texts)
    return manifest
