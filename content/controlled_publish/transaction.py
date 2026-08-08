"""Durable publish transaction model."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from content.controlled_publish.modes import ExecutionMode
from utils.helpers import now_iso


class ChannelPublishState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PREPARED = "PREPARED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"


class TransactionOverallState(str, Enum):
    READY = "READY"
    PUBLISHING = "PUBLISHING"
    PARTIALLY_PUBLISHED = "PARTIALLY_PUBLISHED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass
class ChannelTxnState:
    state: ChannelPublishState = ChannelPublishState.NOT_STARTED
    attempts: int = 0
    last_error: str = ""
    receipt_id: str = ""
    rollback_supported: bool = False
    wechat_step: str = ""  # CREATE_DRAFT | FREEPUBLISH | ""

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "receipt_id": self.receipt_id,
            "rollback_supported": self.rollback_supported,
            "wechat_step": self.wechat_step,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> ChannelTxnState:
        data = data or {}
        return cls(
            state=ChannelPublishState(data.get("state") or ChannelPublishState.NOT_STARTED.value),
            attempts=int(data.get("attempts") or 0),
            last_error=str(data.get("last_error") or ""),
            receipt_id=str(data.get("receipt_id") or ""),
            rollback_supported=bool(data.get("rollback_supported")),
            wechat_step=str(data.get("wechat_step") or ""),
        )


@dataclass
class PublishTransaction:
    transaction_id: str
    release_candidate_id: str
    content_id: str
    revision: str
    execution_mode: str
    started_at: str
    completed_at: str = ""
    overall_state: TransactionOverallState = TransactionOverallState.READY
    website: ChannelTxnState = field(default_factory=ChannelTxnState)
    wechat: ChannelTxnState = field(default_factory=ChannelTxnState)
    attempts: int = 0
    idempotency_keys: dict = field(default_factory=dict)
    receipts: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    network_calls: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "release_candidate_id": self.release_candidate_id,
            "content_id": self.content_id,
            "revision": self.revision,
            "execution_mode": self.execution_mode,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "overall_state": self.overall_state.value,
            "website_state": self.website.to_dict(),
            "wechat_state": self.wechat.to_dict(),
            "attempts": self.attempts,
            "idempotency_keys": dict(self.idempotency_keys),
            "receipts": list(self.receipts),
            "errors": list(self.errors),
            "network_calls": list(self.network_calls),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PublishTransaction:
        return cls(
            transaction_id=str(data["transaction_id"]),
            release_candidate_id=str(data["release_candidate_id"]),
            content_id=str(data["content_id"]),
            revision=str(data["revision"]),
            execution_mode=str(data.get("execution_mode") or ExecutionMode.DRY_RUN.value),
            started_at=str(data.get("started_at") or ""),
            completed_at=str(data.get("completed_at") or ""),
            overall_state=TransactionOverallState(
                data.get("overall_state") or TransactionOverallState.READY.value
            ),
            website=ChannelTxnState.from_dict(data.get("website_state")),
            wechat=ChannelTxnState.from_dict(data.get("wechat_state")),
            attempts=int(data.get("attempts") or 0),
            idempotency_keys=dict(data.get("idempotency_keys") or {}),
            receipts=list(data.get("receipts") or []),
            errors=list(data.get("errors") or []),
            network_calls=list(data.get("network_calls") or []),
            metadata=dict(data.get("metadata") or {}),
        )

    def recompute_overall(self) -> TransactionOverallState:
        w = self.website.state
        c = self.wechat.state
        success = {ChannelPublishState.SUCCEEDED}
        failish = {
            ChannelPublishState.FAILED,
            ChannelPublishState.VERIFICATION_FAILED,
            ChannelPublishState.ROLLBACK_FAILED,
        }
        if w in success and c in success:
            self.overall_state = TransactionOverallState.PUBLISHED
            self.completed_at = self.completed_at or now_iso()
        elif w in success or c in success:
            if w in failish or c in failish or w == ChannelPublishState.IN_PROGRESS or c == ChannelPublishState.IN_PROGRESS:
                self.overall_state = TransactionOverallState.PARTIALLY_PUBLISHED
            else:
                self.overall_state = TransactionOverallState.PARTIALLY_PUBLISHED
        elif w in failish and c in failish:
            self.overall_state = TransactionOverallState.FAILED
        elif w in failish or c in failish:
            self.overall_state = TransactionOverallState.RECOVERY_REQUIRED
        elif w == ChannelPublishState.IN_PROGRESS or c == ChannelPublishState.IN_PROGRESS:
            self.overall_state = TransactionOverallState.PUBLISHING
        else:
            self.overall_state = TransactionOverallState.READY
        return self.overall_state


def new_transaction_id() -> str:
    return f"txn-{uuid.uuid4().hex[:16]}"


class TransactionStore:
    """Durable JSON store for publish transactions (runtime only)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load_all(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return dict(raw.get("transactions") or {})

    def _save_all(self, items: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"transactions": items, "updated_at": now_iso()}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def upsert(self, txn: PublishTransaction) -> PublishTransaction:
        items = self._load_all()
        items[txn.transaction_id] = txn.to_dict()
        self._save_all(items)
        return txn

    def get(self, transaction_id: str) -> PublishTransaction | None:
        data = self._load_all().get(transaction_id)
        return PublishTransaction.from_dict(data) if data else None

    def find_open_for_rc(self, release_candidate_id: str, revision: str) -> PublishTransaction | None:
        for data in self._load_all().values():
            if data.get("release_candidate_id") != release_candidate_id:
                continue
            if data.get("revision") != revision:
                continue
            state = data.get("overall_state")
            if state in (
                TransactionOverallState.PUBLISHED.value,
                TransactionOverallState.FAILED.value,
            ):
                # Still return published for idempotent re-entry
                if state == TransactionOverallState.PUBLISHED.value:
                    return PublishTransaction.from_dict(data)
                continue
            return PublishTransaction.from_dict(data)
        return None

    def list_for_rc(self, release_candidate_id: str) -> list[PublishTransaction]:
        out = [
            PublishTransaction.from_dict(d)
            for d in self._load_all().values()
            if d.get("release_candidate_id") == release_candidate_id
        ]
        return sorted(out, key=lambda t: t.started_at)
