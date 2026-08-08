"""Load and expand Source Discovery query registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REGISTRY_PATH = Path("config/source_queries.yaml")


@dataclass(frozen=True)
class QueryPlan:
    """Resolved search queries for one discover run."""

    mode: str  # query | topic | company
    label: str
    queries: list[str]
    max_queries_per_run: int


def load_query_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Query registry not found: {target}")
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Query registry must be a mapping: {target}")
    return data


def resolve_queries(
    *,
    query: str | None = None,
    topic: str | None = None,
    company: str | None = None,
    registry: dict[str, Any] | None = None,
    registry_path: str | Path | None = None,
    max_queries: int | None = None,
) -> QueryPlan:
    """Resolve CLI inputs into a bounded query list.

    Exactly one of ``query`` / ``topic`` / ``company`` should be provided.
    """
    selected = [bool(query), bool(topic), bool(company)]
    if sum(selected) != 1:
        raise ValueError("Provide exactly one of --query, --topic, or --company")

    data = registry if registry is not None else load_query_registry(registry_path)
    budget = int(
        max_queries
        if max_queries is not None
        else data.get("max_queries_per_run")
        or 4
    )
    budget = max(1, budget)

    if query:
        q = str(query).strip()
        if not q:
            raise ValueError("--query must be non-empty")
        return QueryPlan(mode="query", label=q, queries=[q], max_queries_per_run=budget)

    if topic:
        topics = data.get("topics") or {}
        if not isinstance(topics, dict) or topic not in topics:
            known = ", ".join(sorted(topics)) if isinstance(topics, dict) else ""
            raise KeyError(f"Unknown topic '{topic}'. Known: {known}")
        entry = topics[topic] or {}
        label = str(entry.get("label") or topic)
        raw_queries = entry.get("queries") or []
        queries = [str(item).strip() for item in raw_queries if str(item).strip()]
        if not queries:
            raise ValueError(f"Topic '{topic}' has no queries configured")
        return QueryPlan(
            mode="topic",
            label=label,
            queries=queries[:budget],
            max_queries_per_run=budget,
        )

    company_name = str(company).strip()
    templates = data.get("company_query_templates") or []
    if not isinstance(templates, list) or not templates:
        raise ValueError("company_query_templates missing in query registry")
    queries = []
    for template in templates:
        text = str(template).replace("{company}", company_name).strip()
        if text:
            queries.append(text)
    if not queries:
        raise ValueError(f"No company queries generated for '{company_name}'")
    return QueryPlan(
        mode="company",
        label=company_name,
        queries=queries[:budget],
        max_queries_per_run=budget,
    )
