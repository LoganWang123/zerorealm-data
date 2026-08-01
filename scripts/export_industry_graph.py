"""Export the curated research graph into a portable website snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from knowledge.foundation_graph import build_public_snapshot, seed_foundation_graph
from knowledge.store import KnowledgeStore


def export_industry_graph_snapshot(output: Path, knowledge_path: Path) -> dict:
    """Seed the approved node universe and write only public-safe graph facts."""
    store = KnowledgeStore(str(knowledge_path))
    seed_foundation_graph(store)
    payload = build_public_snapshot(store)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--knowledge-path", type=Path, default=Path("data/knowledge/kb.json"))
    args = parser.parse_args()
    export_industry_graph_snapshot(args.output, args.knowledge_path)


if __name__ == "__main__":
    main()
