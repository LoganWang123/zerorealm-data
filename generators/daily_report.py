"""Daily report generator: crawled data → LLM → MDX.

Refactored to use AI Runtime (LLMClient + PromptRegistry).
Falls back to legacy hardcoded prompts when config/prompts/ is missing.
"""

import json
import os
import glob
from datetime import datetime

import yaml

from utils.logger import get_logger
from utils.helpers import CST

# Source display names
SOURCE_NAMES = {
    "36kr_rss": "36氪",
    "ubox_web": "友宝官网",
    "linkshop_web": "联商网",
}


def load_daily_items(base_dir: str = "data", date: str | None = None) -> list[dict]:
    """Load all raw JSON items for a given date and apply boost scoring."""
    if not date:
        date = datetime.now(CST).strftime("%Y/%m/%d")
    elif "-" in date:
        # Convert YYYY-MM-DD to YYYY/MM/DD
        date = date.replace("-", "/")

    pattern = os.path.join(base_dir, "raw", date, "*.json")
    items = []
    for filepath in glob.glob(pattern):
        with open(filepath, "r", encoding="utf-8") as f:
            items.append(json.load(f))

    # Apply boost scoring if not already present
    if items and "boost_score" not in items[0].get("metadata", {}):
        from processors.boost import score_item, load_boost_config
        try:
            config = load_boost_config()
            for item in items:
                from crawlers.base import RawItem
                raw = RawItem(**item)
                score, matched = score_item(raw, config)
                item["metadata"]["boost_score"] = score
                item["metadata"]["boost_matched"] = matched
                if score >= 10:
                    item["metadata"]["boost_level"] = "star"
                elif score >= 5:
                    item["metadata"]["boost_level"] = "priority"
                else:
                    item["metadata"]["boost_level"] = "normal"
            # Sort by boost score
            items.sort(key=lambda x: x.get("metadata", {}).get("boost_score", 0), reverse=True)
        except Exception:
            pass  # Boost config not available, skip

    return items


def format_materials(items: list[dict]) -> str:
    """Format items as readable materials for LLM prompt.

    Enriched with NER entities/events, quality score, and dedup info
    when available in metadata.
    """
    import re

    lines = []
    for i, item in enumerate(items, 1):
        meta = item.get("metadata", {})
        source_name = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))
        title = item.get("title", "")
        summary = item.get("summary", "")[:200]
        url = item.get("url", "")
        boost_level = meta.get("boost_level", "normal")
        boost_score = meta.get("boost_score", 0)
        quality_score = meta.get("quality_score")
        dedup_role = meta.get("dedup_role")

        # Skip semantic duplicates (keep only representatives)
        if dedup_role == "duplicate":
            continue

        # Mark boosted items
        prefix = ""
        if boost_level == "star":
            prefix = "⭐"
        elif boost_level == "priority":
            prefix = "▲"

        lines.append(f"{i}. {prefix}[{source_name}] {title}")
        if summary:
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            if clean_summary:
                lines.append(f"   摘要: {clean_summary[:150]}")
        lines.append(f"   链接: {url}")

        # Boost info
        if boost_score > 0:
            matched = meta.get("boost_matched", [])
            lines.append(f"   相关度: {boost_score}分 | 命中: {', '.join(matched[:5])}")

        # Quality score
        if quality_score is not None:
            lines.append(f"   质量分: {quality_score}/100")

        # NER entities & events (when available)
        ner = meta.get("ner", {})
        if ner:
            entities = ner.get("entities", [])
            events = ner.get("events", [])
            topics = ner.get("topics", [])
            if entities:
                ent_strs = [f"{e['text']}({e['type']})" for e in entities[:5]]
                lines.append(f"   实体: {', '.join(ent_strs)}")
            if events:
                evt_strs = [f"{e['subject']}{e['action']}" for e in events[:3]]
                lines.append(f"   事件: {'; '.join(evt_strs)}")
            if topics:
                lines.append(f"   主题: {', '.join(topics[:4])}")

        lines.append("")

    return "\n".join(lines)


def _compose_system_prompt() -> str:
    """Compose system prompt from modular files in config/prompts/daily/."""
    daily_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "prompts", "daily"
    )
    # Order matters: role → style → insight → schema → seo
    module_files = ["role.yaml", "style.yaml", "insight.yaml", "schema.yaml", "seo.yaml"]
    parts = []
    for fname in module_files:
        fpath = os.path.join(daily_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            # Each file has a single top-level key containing the text
            for key, value in data.items():
                if isinstance(value, str):
                    parts.append(value.strip())
    return "\n\n".join(parts)


def _load_output_template() -> str:
    """Load the output YAML template from modular file."""
    tpl_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config", "prompts", "daily", "output_template.yaml"
    )
    if os.path.exists(tpl_path):
        with open(tpl_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("output_template", "")
    return ""


def call_llm(materials: str, count: int, issue: int, date: str) -> str:
    """Call LLM API to generate daily report via AI Runtime."""
    logger = get_logger()

    from ai_runtime.client import LLMClient
    from ai_runtime.prompt_registry import PromptRegistry

    # Compose system prompt from modular files
    system = _compose_system_prompt()
    output_tpl = _load_output_template()

    # Build user prompt
    user = (
        f"以下是今日采集的 {count} 条资讯素材。请生成 V4 行业决策情报简报。\n\n"
        f"期号：No.{issue}\n"
        f"日期：{date}\n"
        f"Signal编号：{issue}\n\n"
        f"## 今日素材\n\n{materials}\n\n---\n\n{output_tpl}"
    )

    # Load model config from main yaml
    registry = PromptRegistry()
    tpl = registry.get("daily_report")
    model = tpl.model if tpl else None
    temperature = tpl.temperature if tpl else 0.4
    max_tokens = tpl.max_tokens if tpl else 16000

    client = LLMClient()
    logger.info("[daily] Calling LLM (%s) with %d items...", model or client.model, count)

    resp = client.chat(
        task="daily_report",
        system=system,
        user=user,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt_name="daily_report",
        prompt_version=5,
    )

    logger.info("[daily] LLM response: %d chars", len(resp.content))
    return resp.content


def parse_llm_response(response: str) -> dict:
    """Parse YAML from LLM response."""
    # Extract YAML block if wrapped in ```yaml ... ```
    if "```yaml" in response:
        response = response.split("```yaml")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]

    return yaml.safe_load(response.strip())


def generate_mdx(parsed: dict, issue: int, date: str) -> str:
    """Generate MDX content matching website format (v4: 行业决策解释器)."""
    date_str = date.replace("/", "-") if "/" in date else date

    # Use wechat_title if available, fallback to standard title
    wechat_title = parsed.get("wechat_title", "")
    title = wechat_title if wechat_title else f"零域日报 No.{issue}"

    # Build frontmatter with v4 fields
    fm = {
        "title": title,
        "date": date_str,
        "issue": issue,
        "signal_no": parsed.get("signal_no", issue),
        "ceo_action": parsed.get("ceo_action", []),
        "summary": parsed.get("summary", []),
        "trend": parsed.get("trend", ""),
        "industry_temp": parsed.get("industry_temp", {}),
        "sections": parsed.get("sections", []),
    }

    # Optional v4 fields
    if parsed.get("exclusive_data"):
        fm["exclusive_data"] = parsed["exclusive_data"]
    if parsed.get("data_point"):
        fm["data_point"] = parsed["data_point"]
    if parsed.get("prediction"):
        fm["prediction"] = parsed["prediction"]
    if parsed.get("counter_view"):
        fm["counter_view"] = parsed["counter_view"]
    if parsed.get("signal"):
        fm["signal"] = parsed["signal"]
    if parsed.get("discussion"):
        fm["discussion"] = parsed["discussion"]
    if parsed.get("tomorrow"):
        fm["tomorrow"] = parsed["tomorrow"]

    # Backward compat: keep heat_index if present
    if parsed.get("heat_index"):
        fm["heat_index"] = parsed["heat_index"]
    if parsed.get("opinion"):
        fm["opinion"] = parsed["opinion"]

    # Convert to YAML frontmatter
    frontmatter = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)

    mdx = f"---\n{frontmatter}---\n"
    return mdx


def generate_daily_report(
    base_dir: str = "data",
    output_dir: str = "output_daily",
    date: str | None = None,
    issue: int | None = None,
) -> str | None:
    """Main entry: generate daily report from crawled data.

    Returns path to generated MDX file, or None if no data.
    """
    logger = get_logger()

    if not date:
        date = datetime.now(CST).strftime("%Y-%m-%d")

    date_path = date.replace("-", "/")

    # Load items
    items = load_daily_items(base_dir, date_path)
    if not items:
        logger.warning(f"[daily] No items found for {date}")
        return None

    # Auto issue number (count existing files)
    if issue is None:
        os.makedirs(output_dir, exist_ok=True)
        existing = glob.glob(os.path.join(output_dir, "*.mdx"))
        issue = len(existing) + 1

    # Format materials
    materials = format_materials(items)

    # Call LLM
    response = call_llm(materials, len(items), issue, date)

    # Parse response
    try:
        parsed = parse_llm_response(response)
    except Exception as e:
        logger.error(f"[daily] Failed to parse LLM response: {e}")
        # Save raw response for debugging
        debug_path = os.path.join(output_dir, f"{date}_debug.txt")
        os.makedirs(output_dir, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(response)
        return None

    # Generate MDX
    mdx_content = generate_mdx(parsed, issue, date)

    # Write output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{date}.mdx")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(mdx_content)

    logger.info(f"[daily] Generated: {output_path} (No.{issue})")
    return output_path
