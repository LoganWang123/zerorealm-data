"""Migrate website industry-map hardcodes into research catalog as draft only."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.models import CaseStudy, CompanyProfile, make_source_id


def _slugify(name: str) -> str:
    digest = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return digest[:48] or "company"


def load_graph_nodes(website_root: Path) -> list[dict]:
    path = website_root / "lib" / "industry-graph.ts"
    text = path.read_text(encoding="utf-8")
    # Prefer JSON twin if present
    json_path = website_root / "data" / "industry-graph.json"
    if json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "nodes" in data:
            return list(data["nodes"])
        if isinstance(data, list):
            return data
    # Minimal parse fallback: extract name fields from TS object literals
    names = re.findall(r'name:\s*"([^"]+)"', text)
    roles = re.findall(r'role:\s*"([^"]+)"', text)
    nodes = []
    for index, name in enumerate(names):
        nodes.append(
            {
                "name": name,
                "role": roles[index] if index < len(roles) else "",
                "claim": "",
                "products": [],
                "scenarios": [],
            }
        )
    return nodes


def migrate(*, website_root: Path, catalog_path: Path, write: bool) -> dict:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    existing_names = {item["name"] for item in catalog.get("companies", [])}
    nodes = load_graph_nodes(website_root)
    planned = []
    for node in nodes:
        name = node.get("name") or node.get("label")
        if not name or name in existing_names:
            continue
        slug = node.get("id") or node.get("slug") or _slugify(name)
        company = {
            "id": f"co-mig-{slug}"[:32],
            "slug": str(slug)[:48],
            "name": name,
            "summary": node.get("claim") or f"{name}（industry-map 迁移草稿，待核验）",
            "core_business": node.get("role") or node.get("coreBusiness") or "",
            "products": list(node.get("products") or []),
            "scenarios": list(node.get("scenarios") or []),
            "business_model": "",
            "related_case_ids": [],
            "related_signal_ids": [],
            "verified_at": "",
            "status": "draft",
        }
        planned.append(company)

    report = {
        "mode": "write" if write else "dry-run",
        "plannedCompanies": len(planned),
        "names": [item["name"] for item in planned],
        "autoApproved": False,
    }
    if write and planned:
        catalog.setdefault("companies", []).extend(planned)
        catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--website-root", type=Path, default=Path("../zerorealm-website"))
    parser.add_argument("--catalog", type=Path, default=Path("data/research/public-catalog.json"))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()
    write = bool(args.write)
    report = migrate(website_root=args.website_root, catalog_path=args.catalog, write=write)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
