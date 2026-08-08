"""Load and expand Source Discovery query registry."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    intent: str = "research"
    freshness_window: str | None = None
    priority: int = 0
    max_results: int | None = None
    topic_terms: list[str] = field(default_factory=list)
    company_terms: list[str] = field(default_factory=list)


def load_query_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Query registry not found: {target}")
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Query registry must be a mapping: {target}")
    return data


def _defaults(data: dict[str, Any]) -> dict[str, Any]:
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    return {
        "intent": str(defaults.get("intent") or data.get("intent") or "research"),
        "freshness_window": defaults.get("freshness_window", data.get("freshness_window")),
        "priority": int(defaults.get("priority") or 0),
        "max_results": defaults.get("max_results"),
    }


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
    base = _defaults(data)

    if query:
        q = str(query).strip()
        if not q:
            raise ValueError("--query must be non-empty")
        return QueryPlan(
            mode="query",
            label=q,
            queries=[q],
            max_queries_per_run=budget,
            intent=str(base["intent"]),
            freshness_window=(
                str(base["freshness_window"]) if base["freshness_window"] else None
            ),
            priority=int(base["priority"]),
            max_results=int(base["max_results"]) if base["max_results"] else None,
            topic_terms=[q],
        )

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
        intent = str(entry.get("intent") or base["intent"] or "research")
        window = entry.get("freshness_window", base["freshness_window"])
        priority = int(entry.get("priority") if entry.get("priority") is not None else base["priority"])
        max_results = entry.get("max_results", base["max_results"])
        return QueryPlan(
            mode="topic",
            label=label,
            queries=queries[:budget],
            max_queries_per_run=budget,
            intent=intent,
            freshness_window=str(window) if window else None,
            priority=priority,
            max_results=int(max_results) if max_results else None,
            topic_terms=list(dict.fromkeys([label, *queries[:budget]])),
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

    companies = data.get("companies") or []
    company_meta: dict[str, Any] = {}
    if isinstance(companies, dict) and company_name in companies:
        company_meta = companies[company_name] or {}
    elif isinstance(companies, list):
        for row in companies:
            if isinstance(row, str) and row.strip() == company_name:
                company_meta = {}
                break
            if isinstance(row, dict) and str(row.get("name") or "") == company_name:
                company_meta = row
                break

    intent = str(company_meta.get("intent") or base["intent"] or "research")
    window = company_meta.get("freshness_window", base["freshness_window"])
    priority = int(
        company_meta.get("priority")
        if company_meta.get("priority") is not None
        else base["priority"]
    )
    max_results = company_meta.get("max_results", base["max_results"])
    return QueryPlan(
        mode="company",
        label=company_name,
        queries=queries[:budget],
        max_queries_per_run=budget,
        intent=intent,
        freshness_window=str(window) if window else None,
        priority=priority,
        max_results=int(max_results) if max_results else None,
        company_terms=[company_name],
        topic_terms=[],
    )
