"""Controlled publish service — transactions, locks, verify, fake execute."""

from __future__ import annotations

from pathlib import Path

from content.controlled_publish.confirmation import build_confirmation_token, validate_confirmation_token
from content.controlled_publish.errors import (
    CONFIRMATION_REQUIRED,
    NOT_READY_FOR_PUBLISH,
    PRODUCTION_MODE_REQUIRED,
    PUBLISH_DISABLED,
    ControlledPublishError,
)
from content.controlled_publish.factory import ControlledPublisherFactory
from content.controlled_publish.lock import ReleaseLockStore
from content.controlled_publish.modes import ExecutionMode, publish_disabled, resolve_execution_mode
from content.controlled_publish.receipt import ReceiptStore, make_idempotency_key
from content.controlled_publish.rollback import build_recovery_plan
from content.controlled_publish.transaction import (
    ChannelPublishState,
    PublishTransaction,
    TransactionOverallState,
    TransactionStore,
    new_transaction_id,
)
from content.controlled_publish.verify import MockWeChatVerifier, MockWebsiteVerifier, VerifyResult
from content.controlled_publish.wechat_adapter import WeChatPublishStep
from content.orchestrator import ReleaseOrchestrator
from content.release_candidate import ReleaseCandidate, ReleaseCandidateStatus
from utils.helpers import now_iso


class ControlledPublishService:
    """Coordinates safe fake publish. Real PRODUCTION side effects remain blocked by default."""

    def __init__(
        self,
        *,
        factory: ControlledPublisherFactory | None = None,
        txn_store: TransactionStore | None = None,
        receipt_store: ReceiptStore | None = None,
        lock_store: ReleaseLockStore | None = None,
        website_verifier: MockWebsiteVerifier | None = None,
        wechat_verifier: MockWeChatVerifier | None = None,
        orchestrator: ReleaseOrchestrator | None = None,
        root: str | Path | None = None,
    ):
        base = Path(root or "data/state/controlled_publish")
        self.factory = factory or ControlledPublisherFactory()
        self.txn_store = txn_store or TransactionStore(base / "transactions.json")
        self.receipt_store = receipt_store or ReceiptStore(base / "receipts.jsonl")
        self.lock_store = lock_store or ReleaseLockStore(base / "locks.json")
        self.website_verifier = website_verifier or MockWebsiteVerifier()
        self.wechat_verifier = wechat_verifier or MockWeChatVerifier()
        self.orchestrator = orchestrator or ReleaseOrchestrator()

    def confirmation_token(self, rc: ReleaseCandidate) -> str:
        return build_confirmation_token(rc)

    def prepare_all(self, rc: ReleaseCandidate) -> dict:
        status = self.orchestrator.preflight(rc)
        website = self.factory.website().prepare(rc) if status.ready else None
        wechat = self.factory.wechat().prepare(rc) if status.ready else None
        return {
            "ready": status.ready,
            "blocking_reasons": status.blocking_reasons,
            "website": website,
            "wechat": wechat,
            "confirmation_token_hint": "run confirmation-token command after READY",
        }

    def _require_ready(self, rc: ReleaseCandidate) -> None:
        status = self.orchestrator.preflight(rc)
        if not status.ready or rc.status is not ReleaseCandidateStatus.READY_FOR_PUBLISH:
            raise ControlledPublishError(
                NOT_READY_FOR_PUBLISH,
                ",".join(status.blocking_reasons) or "not READY_FOR_PUBLISH",
            )

    def _guard_execute(
        self,
        rc: ReleaseCandidate,
        *,
        mode: ExecutionMode,
        confirm: str | None,
        env: dict[str, str] | None,
        require_confirm: bool,
    ) -> None:
        if publish_disabled(env):
            raise ControlledPublishError(PUBLISH_DISABLED, "PUBLISH_DISABLED=true")
        self._require_ready(rc)
        if mode is ExecutionMode.PRODUCTION and require_confirm:
            validate_confirmation_token(rc, confirm)
        elif mode is ExecutionMode.STAGING and require_confirm:
            # Staging also requires explicit confirmation when executing
            validate_confirmation_token(rc, confirm)
        elif mode is ExecutionMode.PRODUCTION and not require_confirm:
            raise ControlledPublishError(CONFIRMATION_REQUIRED, "PRODUCTION requires confirmation")

    def get_or_create_transaction(
        self,
        rc: ReleaseCandidate,
        *,
        mode: ExecutionMode,
    ) -> PublishTransaction:
        existing = self.txn_store.find_open_for_rc(rc.release_candidate_id, rc.revision)
        if existing:
            return existing
        txn = PublishTransaction(
            transaction_id=new_transaction_id(),
            release_candidate_id=rc.release_candidate_id,
            content_id=rc.content_id,
            revision=rc.revision,
            execution_mode=mode.value,
            started_at=now_iso(),
            overall_state=TransactionOverallState.READY,
            website=txn_channel_defaults(website=True),
            wechat=txn_channel_defaults(website=False),
            idempotency_keys={
                "website": make_idempotency_key(rc.release_candidate_id, "website", rc.revision),
                "wechat": make_idempotency_key(rc.release_candidate_id, "wechat", rc.revision),
            },
        )
        return self.txn_store.upsert(txn)

    def execute(
        self,
        rc: ReleaseCandidate,
        *,
        mode: str | ExecutionMode = ExecutionMode.DRY_RUN,
        confirm: str | None = None,
        channels: list[str] | None = None,
        freepublish_approved: bool = False,
        env: dict[str, str] | None = None,
        acquire_lock: bool = True,
    ) -> dict:
        mode_e = resolve_execution_mode(mode)
        if mode_e is ExecutionMode.DRY_RUN:
            prepared = self.prepare_all(rc)
            return {
                "ok": True,
                "mode": mode_e.value,
                "executed": False,
                "prepared": prepared,
                "network_calls": [],
                "website_production_writes": 0,
                "wechat_api_calls": 0,
            }

        # Non-dry-run still blocked by default kill switch.
        self._guard_execute(rc, mode=mode_e, confirm=confirm, env=env, require_confirm=True)

        lock = None
        if acquire_lock:
            lock = self.lock_store.acquire(rc.release_candidate_id)
        try:
            txn = self.get_or_create_transaction(rc, mode=mode_e)
            if txn.overall_state is TransactionOverallState.PUBLISHED:
                return {
                    "ok": True,
                    "mode": mode_e.value,
                    "executed": False,
                    "idempotent": True,
                    "transaction": txn.to_dict(),
                    "receipts": txn.receipts,
                    "network_calls": [],
                }

            targets = channels or ["website", "wechat"]
            txn.attempts += 1
            txn.overall_state = TransactionOverallState.PUBLISHING
            self.txn_store.upsert(txn)

            if "website" in targets:
                self._run_website(rc, txn, mode_e, env=env)
            if "wechat" in targets:
                self._run_wechat(
                    rc,
                    txn,
                    mode_e,
                    env=env,
                    freepublish_approved=freepublish_approved,
                )

            txn.recompute_overall()
            self.txn_store.upsert(txn)
            return {
                "ok": txn.overall_state is TransactionOverallState.PUBLISHED,
                "mode": mode_e.value,
                "executed": True,
                "transaction": txn.to_dict(),
                "receipts": txn.receipts,
                "network_calls": list(txn.network_calls),
                "website_production_writes": 0,
                "wechat_api_calls": 0,
                "lock": lock.to_dict() if lock else None,
            }
        finally:
            if lock:
                self.lock_store.release(rc.release_candidate_id, owner=lock.locked_by)

    def retry(
        self,
        transaction_id: str,
        rc: ReleaseCandidate,
        *,
        channel: str,
        confirm: str | None = None,
        freepublish_approved: bool = False,
        env: dict[str, str] | None = None,
    ) -> dict:
        txn = self.txn_store.get(transaction_id)
        if txn is None:
            raise ControlledPublishError("TRANSACTION_NOT_FOUND", transaction_id)
        mode_e = resolve_execution_mode(txn.execution_mode)
        self._guard_execute(rc, mode=mode_e, confirm=confirm, env=env, require_confirm=True)

        # Skip channels already succeeded
        if channel == "website" and txn.website.state is ChannelPublishState.SUCCEEDED:
            return {
                "ok": True,
                "skipped": True,
                "reason": "website already SUCCEEDED",
                "transaction": txn.to_dict(),
            }
        if channel == "wechat" and txn.wechat.state is ChannelPublishState.SUCCEEDED:
            return {
                "ok": True,
                "skipped": True,
                "reason": "wechat already SUCCEEDED",
                "transaction": txn.to_dict(),
            }

        lock = self.lock_store.acquire(rc.release_candidate_id)
        try:
            txn.attempts += 1
            if channel == "website":
                self._run_website(rc, txn, mode_e, env=env)
            elif channel == "wechat":
                self._run_wechat(
                    rc,
                    txn,
                    mode_e,
                    env=env,
                    freepublish_approved=freepublish_approved,
                )
            else:
                raise ControlledPublishError("UNKNOWN_CHANNEL", channel)
            txn.recompute_overall()
            self.txn_store.upsert(txn)
            return {
                "ok": txn.overall_state is TransactionOverallState.PUBLISHED,
                "transaction": txn.to_dict(),
                "network_calls": [],
            }
        finally:
            self.lock_store.release(rc.release_candidate_id, owner=lock.locked_by)

    def _run_website(
        self,
        rc: ReleaseCandidate,
        txn: PublishTransaction,
        mode: ExecutionMode,
        *,
        env: dict[str, str] | None,
    ) -> None:
        if txn.website.state is ChannelPublishState.SUCCEEDED:
            return
        pub = self.factory.website()
        txn.website.state = ChannelPublishState.IN_PROGRESS
        txn.website.attempts += 1
        self.txn_store.upsert(txn)
        try:
            # Idempotent: reuse receipt
            existing = self.receipt_store.find_by_idempotency(
                txn.idempotency_keys["website"], channel="website"
            )
            if existing:
                receipt = existing
            else:
                receipt = pub.execute(rc, mode=mode, env=env)
                receipt = self.receipt_store.append(receipt)
            verify = self.website_verifier.verify(rc, receipt)
            self._apply_verify(txn, "website", receipt, verify)
        except ControlledPublishError as exc:
            txn.website.state = ChannelPublishState.FAILED
            txn.website.last_error = exc.code
            txn.errors.append(f"website:{exc.code}")
            self.txn_store.upsert(txn)

    def _run_wechat(
        self,
        rc: ReleaseCandidate,
        txn: PublishTransaction,
        mode: ExecutionMode,
        *,
        env: dict[str, str] | None,
        freepublish_approved: bool,
    ) -> None:
        if txn.wechat.state is ChannelPublishState.SUCCEEDED:
            return
        pub = self.factory.wechat()
        txn.wechat.state = ChannelPublishState.IN_PROGRESS
        txn.wechat.attempts += 1
        self.txn_store.upsert(txn)
        try:
            key = txn.idempotency_keys["wechat"]
            draft_receipt = None
            for r in self.receipt_store.list_for_rc(rc.release_candidate_id):
                if r.channel == "wechat" and (r.details or {}).get("step") == WeChatPublishStep.CREATE_DRAFT.value:
                    draft_receipt = r
            if draft_receipt is None:
                draft_receipt = pub.execute(
                    rc,
                    mode=mode,
                    step=WeChatPublishStep.CREATE_DRAFT,
                    env=env,
                )
                draft_receipt = self.receipt_store.append(draft_receipt)
                txn.receipts.append(draft_receipt.to_dict())

            if not freepublish_approved:
                txn.wechat.state = ChannelPublishState.FAILED
                txn.wechat.last_error = "FREEPUBLISH_NOT_APPROVED"
                txn.wechat.wechat_step = WeChatPublishStep.CREATE_DRAFT.value
                txn.errors.append("wechat:FREEPUBLISH_NOT_APPROVED")
                self.txn_store.upsert(txn)
                return

            # Idempotent freepublish receipt
            existing_fp = None
            for r in self.receipt_store.list_for_rc(rc.release_candidate_id):
                if r.channel == "wechat" and (r.details or {}).get("step") == WeChatPublishStep.FREEPUBLISH.value:
                    existing_fp = r
            if existing_fp:
                receipt = existing_fp
            else:
                receipt = pub.execute(
                    rc,
                    mode=mode,
                    step=WeChatPublishStep.FREEPUBLISH,
                    freepublish_approved=True,
                    existing_draft_receipt=draft_receipt,
                    env=env,
                )
                receipt = self.receipt_store.append(receipt)
            verify = self.wechat_verifier.verify(rc, receipt)
            self._apply_verify(txn, "wechat", receipt, verify)
            txn.wechat.wechat_step = WeChatPublishStep.FREEPUBLISH.value
        except ControlledPublishError as exc:
            txn.wechat.state = ChannelPublishState.FAILED
            txn.wechat.last_error = exc.code
            txn.errors.append(f"wechat:{exc.code}")
            self.txn_store.upsert(txn)

    def _apply_verify(
        self,
        txn: PublishTransaction,
        channel: str,
        receipt,
        verify: VerifyResult,
    ) -> None:
        state = txn.website if channel == "website" else txn.wechat
        if verify.ok:
            state.state = ChannelPublishState.SUCCEEDED
            state.receipt_id = receipt.receipt_id
            state.last_error = ""
            if not any(r.get("receipt_id") == receipt.receipt_id for r in txn.receipts):
                txn.receipts.append(receipt.to_dict())
        else:
            state.state = ChannelPublishState.VERIFICATION_FAILED
            state.last_error = ",".join(verify.reasons)
            txn.errors.append(f"{channel}:VERIFICATION_FAILED")
        self.txn_store.upsert(txn)

    def recovery_plan(self, transaction_id: str) -> dict:
        txn = self.txn_store.get(transaction_id)
        if txn is None:
            raise ControlledPublishError("TRANSACTION_NOT_FOUND", transaction_id)
        return build_recovery_plan(txn).to_dict()


def txn_channel_defaults(*, website: bool):
    from content.controlled_publish.transaction import ChannelTxnState

    return ChannelTxnState(
        state=ChannelPublishState.NOT_STARTED,
        rollback_supported=website,
    )


def assert_production_blocked_without_mode():
    """Helper documenting that API keys alone never enable PRODUCTION."""
    raise ControlledPublishError(
        PRODUCTION_MODE_REQUIRED,
        "API keys do not enable PRODUCTION; pass explicit --mode production + confirmation",
    )
