"""Runtime LLM call ledger — never commit outputs."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from utils.helpers import now_iso


@dataclass
class LedgerEntry:
    run_id: str
    content_id: str
    provider: str
    model: str
    task: str
    prompt_version: int | None = None
    prompt_hash: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0
    schema_result: str = ""
    gate_result: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class LLMCallLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.entries: list[LedgerEntry] = []

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        if not entry.created_at:
            entry.created_at = now_iso()
        if not entry.run_id:
            entry.run_id = self.run_id
        self.entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_llm_calls": len(self.entries),
            "total_input_tokens": sum(e.input_tokens for e in self.entries),
            "total_output_tokens": sum(e.output_tokens for e in self.entries),
            "estimated_total_cost": round(sum(e.estimated_cost for e in self.entries), 6),
            "models": sorted({e.model for e in self.entries}),
        }
