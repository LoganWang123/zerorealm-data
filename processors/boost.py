"""Keyword Boost: score articles based on industry relevance.

Aligned with Data Strategy V2.0 industry chain model.
"""

import os
import re

import yaml

from crawlers.base import RawItem
from utils.logger import get_logger


_boost_config = None


def load_boost_config(config_path: str = None) -> dict:
    """Load boost configuration from YAML."""
    global _boost_config
    if _boost_config is not None:
        return _boost_config

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "boost.yaml"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        _boost_config = yaml.safe_load(f)

    return _boost_config


def score_item(item: RawItem, config: dict = None) -> tuple[int, list[str]]:
    """Score an item based on keyword boost rules.

    Returns (total_score, matched_keywords).
    """
    if config is None:
        config = load_boost_config()

    # Combine title + summary + content_text for matching
    text = f"{item.title} {item.summary} {item.content_text[:500]}".lower()

    total_score = 0
    matched = []

    # Core keywords (highest weight)
    core = config.get("core_keywords", {})
    core_weight = core.get("weight", 10)
    for kw in core.get("keywords", []):
        if kw.lower() in text:
            total_score += core_weight
            matched.append(f"core:{kw}")

    # Role keywords
    for role, role_config in config.get("role_keywords", {}).items():
        weight = role_config.get("weight", 5)
        for kw in role_config.get("keywords", []):
            if kw.lower() in text:
                total_score += weight
                matched.append(f"{role}:{kw}")

    # Event keywords
    for event, event_config in config.get("event_keywords", {}).items():
        weight = event_config.get("weight", 5)
        for kw in event_config.get("keywords", []):
            if kw.lower() in text:
                total_score += weight
                matched.append(f"event:{kw}")

    # Company keywords
    company = config.get("company_keywords", {})
    company_weight = company.get("weight", 5)
    for kw in company.get("keywords", []):
        if kw.lower() in text:
            total_score += company_weight
            matched.append(f"company:{kw}")

    return total_score, matched


def apply_boost(items: list[RawItem], config: dict = None) -> list[RawItem]:
    """Apply boost scoring to all items, sort by score descending.

    Adds 'boost_score' and 'boost_matched' to item.metadata.
    """
    if config is None:
        config = load_boost_config()

    logger = get_logger()
    rules = config.get("rules", {})
    star_threshold = rules.get("star_threshold", 10)
    priority_threshold = rules.get("priority_threshold", 5)

    for item in items:
        score, matched = score_item(item, config)
        item.metadata["boost_score"] = score
        item.metadata["boost_matched"] = matched

        if score >= star_threshold:
            item.metadata["boost_level"] = "star"
        elif score >= priority_threshold:
            item.metadata["boost_level"] = "priority"
        else:
            item.metadata["boost_level"] = "normal"

    # Sort: star first, then priority, then by score
    items.sort(key=lambda x: x.metadata.get("boost_score", 0), reverse=True)

    star_count = sum(1 for i in items if i.metadata.get("boost_level") == "star")
    priority_count = sum(1 for i in items if i.metadata.get("boost_level") == "priority")
    logger.info(
        f"[boost] Scored {len(items)} items: "
        f"{star_count} star, {priority_count} priority"
    )

    return items
