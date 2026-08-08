"""WeChat controlled publisher adapter — draft vs freepublish separated; fake only in v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from content.controlled_publish.errors import (
    FREEPUBLISH_NOT_APPROVED,
    MEDIA_NOT_APPROVED,
    NETWORK_FORBIDDEN,
    PUBLISH_DISABLED,
    WECHAT_STEP_REQUIRED,
    ControlledPublishError,
)
from content.controlled_publish.modes import ExecutionMode, publish_disabled
from content.controlled_publish.receipt import PublishReceipt, make_idempotency_key, mock_wechat_receipt
from content.publisher_preflight import build_wechat_publish_plan
from content.release_candidate import ReleaseCandidate, assert_ready_for_publish


class WeChatPublishStep(str, Enum):
    CREATE_DRAFT = "CREATE_DRAFT"
    FREEPUBLISH = "FREEPUBLISH"


@dataclass
class FakeWeChatBackend:
    """Never calls real WeChat APIs."""

    drafts: dict[str, dict] = field(default_factory=dict)
    freepublished: set[str] = field(default_factory=set)
    api_calls: list = field(default_factory=list)
    network_calls: list = field(default_factory=list)

    def create_draft(self, *, idempotency_key: str, payload: dict) -> dict:
        if idempotency_key in self.drafts:
            return self.drafts[idempotency_key]
        draft = {
            "draft_media_id": f"mock://wechat/draft/test-{idempotency_key[-12:]}",
            "idempotency_key": idempotency_key,
            "payload": payload,
        }
        self.drafts[idempotency_key] = draft
        return draft

    def freepublish(self, *, idempotency_key: str, draft_media_id: str) -> dict:
        self.freepublished.add(idempotency_key)
        return {
            "publish_id": f"mock://wechat/publish/test-{idempotency_key[-12:]}",
            "draft_media_id": draft_media_id,
        }


def _media_approved(rc: ReleaseCandidate) -> list[dict]:
    media = list((rc.wechat_artifact or {}).get("media") or [])
    # Empty media is allowed for text-only fixtures; pending/rejected block.
    for item in media:
        status = str((item or {}).get("status") or "approved").lower()
        if status in ("pending", "rejected", "failed", "blocked"):
            raise ControlledPublishError(
                MEDIA_NOT_APPROVED,
                f"Media not approved: {item.get('id') or item}",
            )
    return media


class WeChatControlledPublisher:
    channel = "wechat"
    rollback_supported = False

    def __init__(self, backend: FakeWeChatBackend | None = None):
        self.backend = backend or FakeWeChatBackend()

    def prepare(self, rc: ReleaseCandidate) -> dict:
        assert_ready_for_publish(rc)
        plan = build_wechat_publish_plan(rc)
        media = _media_approved(rc)
        return {
            **plan,
            "title": (rc.wechat_artifact or {}).get("title") or rc.slug,
            "summary": (rc.wechat_artifact or {}).get("summary") or "",
            "html_present": bool((rc.wechat_artifact or {}).get("html") or (rc.wechat_artifact or {}).get("body")),
            "media": media,
            "content_fingerprint": rc.content_fingerprint,
            "steps": [WeChatPublishStep.CREATE_DRAFT.value, WeChatPublishStep.FREEPUBLISH.value],
            "auto_freepublish": False,
        }

    def preflight(self, rc: ReleaseCandidate, prepared: dict | None = None) -> dict:
        prepared = prepared or self.prepare(rc)
        if not prepared.get("html_present") and not (rc.wechat_artifact or {}).get("sections"):
            # Allow structured artifact without html key in fixtures
            if not rc.wechat_artifact:
                raise ControlledPublishError(WECHAT_STEP_REQUIRED, "WeChat artifact missing")
        return {"ok": True, "prepared": prepared, "auto_freepublish": False}

    def execute(
        self,
        rc: ReleaseCandidate,
        *,
        mode: ExecutionMode,
        step: WeChatPublishStep,
        freepublish_approved: bool = False,
        prepared: dict | None = None,
        env: dict[str, str] | None = None,
        existing_draft_receipt: PublishReceipt | None = None,
    ) -> PublishReceipt:
        if publish_disabled(env):
            raise ControlledPublishError(PUBLISH_DISABLED, "PUBLISH_DISABLED=true blocks execute")
        if mode is ExecutionMode.DRY_RUN:
            raise ControlledPublishError(NETWORK_FORBIDDEN, "DRY_RUN cannot execute")
        if self.backend.api_calls or self.backend.network_calls:
            raise ControlledPublishError(NETWORK_FORBIDDEN, "Real WeChat API forbidden in v1")

        prepared = prepared or self.prepare(rc)
        self.preflight(rc, prepared)
        key = make_idempotency_key(rc.release_candidate_id, "wechat", rc.revision)

        if step is WeChatPublishStep.CREATE_DRAFT:
            draft = self.backend.create_draft(
                idempotency_key=key,
                payload={
                    "title": prepared["title"],
                    "content_id": rc.content_id,
                    "fingerprint": rc.content_fingerprint,
                },
            )
            return mock_wechat_receipt(
                release_candidate_id=rc.release_candidate_id,
                content_id=rc.content_id,
                revision=rc.revision,
                artifact_hash=prepared["artifact_hash"],
                fingerprint=rc.content_fingerprint,
                step=step.value,
                draft_media_id=draft["draft_media_id"],
            )

        if step is WeChatPublishStep.FREEPUBLISH:
            if not freepublish_approved:
                raise ControlledPublishError(
                    FREEPUBLISH_NOT_APPROVED,
                    "FREEPUBLISH_APPROVED required; draft success must not auto freepublish",
                )
            draft_id = None
            if existing_draft_receipt:
                draft_id = (existing_draft_receipt.details or {}).get("draft_media_id")
            if not draft_id:
                draft = self.backend.drafts.get(key)
                draft_id = (draft or {}).get("draft_media_id")
            if not draft_id:
                raise ControlledPublishError(WECHAT_STEP_REQUIRED, "CREATE_DRAFT receipt required before FREEPUBLISH")
            pub = self.backend.freepublish(idempotency_key=key, draft_media_id=draft_id)
            return mock_wechat_receipt(
                release_candidate_id=rc.release_candidate_id,
                content_id=rc.content_id,
                revision=rc.revision,
                artifact_hash=prepared["artifact_hash"],
                fingerprint=rc.content_fingerprint,
                step=step.value,
                draft_media_id=draft_id,
                publish_id=pub["publish_id"],
            )

        raise ControlledPublishError(WECHAT_STEP_REQUIRED, f"Unknown step: {step}")
