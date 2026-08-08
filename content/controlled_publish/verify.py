"""Post-publish verification (mock in v1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from content.controlled_publish.receipt import PublishReceipt
from content.release_candidate import ReleaseCandidate


@dataclass
class VerifyResult:
    ok: bool
    channel: str
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "channel": self.channel,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


class ChannelVerifier(Protocol):
    def verify(self, rc: ReleaseCandidate, receipt: PublishReceipt) -> VerifyResult: ...


class MockWebsiteVerifier:
    def __init__(self, *, force_fail: bool = False):
        self.force_fail = force_fail
        self.calls: list[str] = []

    def verify(self, rc: ReleaseCandidate, receipt: PublishReceipt) -> VerifyResult:
        self.calls.append(receipt.receipt_id)
        if self.force_fail:
            return VerifyResult(ok=False, channel="website", reasons=["MOCK_VERIFY_FAIL"])
        expected_route = f"/insight/{rc.slug}" if rc.content_type == "insight" else f"/daily/{rc.slug}"
        route = (receipt.details or {}).get("route")
        reasons = []
        if route != expected_route:
            reasons.append("ROUTE_MISMATCH")
        if receipt.fingerprint != rc.content_fingerprint:
            reasons.append("FINGERPRINT_MISMATCH")
        if not str(receipt.receipt_id).startswith("mock://"):
            reasons.append("NON_MOCK_RECEIPT_IN_V1")
        return VerifyResult(
            ok=not reasons,
            channel="website",
            reasons=reasons,
            details={"expected_route": expected_route, "route": route},
        )


class MockWeChatVerifier:
    def __init__(self, *, force_fail: bool = False):
        self.force_fail = force_fail
        self.calls: list[str] = []

    def verify(self, rc: ReleaseCandidate, receipt: PublishReceipt) -> VerifyResult:
        self.calls.append(receipt.receipt_id)
        if self.force_fail:
            return VerifyResult(ok=False, channel="wechat", reasons=["MOCK_VERIFY_FAIL"])
        reasons = []
        if receipt.fingerprint != rc.content_fingerprint:
            reasons.append("FINGERPRINT_MISMATCH")
        draft = (receipt.details or {}).get("draft_media_id") or ""
        if not str(draft).startswith("mock://"):
            reasons.append("NON_MOCK_DRAFT_IN_V1")
        return VerifyResult(ok=not reasons, channel="wechat", reasons=reasons, details={"draft_media_id": draft})
