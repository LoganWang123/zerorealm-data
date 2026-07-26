"""Daily report generator: crawled data → LLM → MDX."""

import json
import os
import glob
from datetime import datetime

import yaml
from openai import OpenAI

from generators.prompts import DAILY_REPORT_SYSTEM, DAILY_REPORT_USER
from utils.logger import get_logger
from utils.helpers import CST

# Source display names
SOURCE_NAMES = {
    "36kr_rss": "36氪",
    "ubox_web": "友宝官网",
    "linkshop_web": "联商网",
}


def load_daily_items(base_dir: str = "data", date: str | None = None) -> list[dict]:
    """Load all raw JSON items for a given date."""
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

    return items


def format_materials(items: list[dict]) -> str:
    """Format items as readable materials for LLM prompt."""
    lines = []
    for i, item in enumerate(items, 1):
        source_name = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))
        title = item.get("title", "")
        summary = item.get("summary", "")[:200]
        url = item.get("url", "")
        category = item.get("metadata", {}).get("category", "news")
        boost_level = item.get("metadata", {}).get("boost_level", "normal")
        boost_score = item.get("metadata", {}).get("boost_score", 0)

        # Mark boosted items
        prefix = ""
        if boost_level == "star":
            prefix = "⭐"
        elif boost_level == "priority":
            prefix = "▲"

        lines.append(f"{i}. {prefix}[{source_name}] {title}")
        if summary:
            # Strip HTML tags from summary
            import re
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            if clean_summary:
                lines.append(f"   摘要: {clean_summary[:150]}")
        lines.append(f"   链接: {url}")
        if boost_score > 0:
            matched = item.get("metadata", {}).get("boost_matched", [])
            lines.append(f"   相关度: {boost_score}分 | 命中: {', '.join(matched[:5])}")
        lines.append("")

    return "\n".join(lines)


def call_llm(materials: str, count: int, issue: int, date: str) -> str:
    """Call LLM API to generate daily report."""
    logger = get_logger()

    client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
    )

    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    user_prompt = DAILY_REPORT_USER.format(
        count=count,
        issue=issue,
        date=date,
        materials=materials,
    )

    logger.info(f"[daily] Calling LLM ({model}) with {count} items...")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": DAILY_REPORT_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    content = response.choices[0].message.content
    logger.info(f"[daily] LLM response: {len(content)} chars")
    return content


def parse_llm_response(response: str) -> dict:
    """Parse YAML from LLM response."""
    # Extract YAML block if wrapped in ```yaml ... ```
    if "```yaml" in response:
        response = response.split("```yaml")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]

    return yaml.safe_load(response.strip())


def generate_mdx(parsed: dict, issue: int, date: str) -> str:
    """Generate MDX content matching website format."""
    date_str = date.replace("/", "-") if "/" in date else date

    # Build frontmatter
    fm = {
        "title": f"零域日报 No.{issue}",
        "date": date_str,
        "issue": issue,
        "summary": parsed.get("summary", []),
        "sections": parsed.get("sections", []),
    }

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
