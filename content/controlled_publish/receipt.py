"""Immutable publish receipts (mock IDs only in v1)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from utils.helpers import now_iso


@dataclass(frozen=True)
class PublishReceipt:
    receipt_id: str
    channel: str
    release_candidate_id: str
    content_id: str
    revision: str
    artifact_hash: str
    fingerprint: str
    published_at: str
    idempotency_key: str
    mock: bool = True
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PublishReceipt:
        return cls(
            receipt_id=str(data["receipt_id"]),
            channel=str(data["channel"]),
            release_candidate_id=str(data["release_candidate_id"]),
            content_id=str(data["content_id"]),
            revision=str(data["revision"]),
            artifact_hash=str(data.get("artifact_hash") or ""),
            fingerprint=str(data.get("fingerprint") or ""),
            published_at=str(data.get("published_at") or ""),
            idempotency_key=str(data.get("idempotency_key") or ""),
            mock=bool(data.get("mock", True)),
            details=dict(data.get("details") or {}),
        )


def make_idempotency_key(release_candidate_id: str, channel: str, revision: str) -> str:
    return f"{release_candidate_id}:{channel}:{revision}"


def mock_website_receipt(
    *,
    release_candidate_id: str,
    content_id: str,
    revision: str,
    artifact_hash: str,
    fingerprint: str,
    route: str,
    content_path: str,
) -> PublishReceipt:
    key = make_idempotency_key(release_candidate_id, "website", revision)
    return PublishReceipt(
        receipt_id=f"mock://website-receipt/{key}",
        channel="website",
        release_candidate_id=release_candidate_id,
        content_id=content_id,
        revision=revision,
        artifact_hash=artifact_hash,
        fingerprint=fingerprint,
        published_at=now_iso(),
        idempotency_key=key,
        mock=True,
        details={
            "commit_sha": "mock://git/commit/test-fake-sha",
            "deployment_id": "mock://vercel/deployment/test-fake",
            "route": route,
            "content_path": content_path,
        },
    )


def mock_wechat_receipt(
    *,
    release_candidate_id: str,
    content_id: str,
    revision: str,
    artifact_hash: str,
    fingerprint: str,
    step: str,
    draft_media_id: str | None = None,
    publish_id: str | None = None,
) -> PublishReceipt:
    key = make_idempotency_key(release_candidate_id, "wechat", revision)
    return PublishReceipt(
        receipt_id=f"mock://wechat-receipt/{key}:{step}",
        channel="wechat",
        release_candidate_id=release_candidate_id,
        content_id=content_id,
        revision=revision,
        artifact_hash=artifact_hash,
        fingerprint=fingerprint,
        published_at=now_iso(),
        idempotency_key=key,
        mock=True,
        details={
            "step": step,
            "draft_media_id": draft_media_id or f"mock://wechat/draft/test-{revision[:8]}",
            "publish_id": publish_id,
        },
    )


class ReceiptStore:
    """Append-only JSONL receipts keyed by idempotency."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, receipt: PublishReceipt) -> PublishReceipt:
        existing = self.find_by_idempotency(receipt.idempotency_key, channel=receipt.channel)
        if existing and existing.details.get("step") == receipt.details.get("step"):
            return existing
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.to_dict(), ensure_ascii=False) + "\n")
        return receipt

    def _iter(self) -> list[PublishReceipt]:
        if not self.path.exists():
            return []
        out: list[PublishReceipt] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(PublishReceipt.from_dict(json.loads(line)))
        return out

    def list_for_rc(self, release_candidate_id: str) -> list[PublishReceipt]:
        return [r for r in self._iter() if r.release_candidate_id == release_candidate_id]

    def find_by_idempotency(self, key: str, *, channel: str | None = None) -> PublishReceipt | None:
        matches = [r for r in self._iter() if r.idempotency_key == key]
        if channel:
            matches = [r for r in matches if r.channel == channel]
        return matches[-1] if matches else None
