"""Rollback capability model — plans only, no production rollback in v1."""

from __future__ import annotations

from dataclasses import dataclass, field

from content.controlled_publish.transaction import ChannelPublishState, PublishTransaction


@dataclass
class ChannelRollbackCapability:
    channel: str
    rollback_supported: bool
    strategy: str
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "rollback_supported": self.rollback_supported,
            "strategy": self.strategy,
            "notes": self.notes,
        }


WEBSITE_ROLLBACK = ChannelRollbackCapability(
    channel="website",
    rollback_supported=True,
    strategy="revert_commit",
    notes="Future: revert content commit + redeploy. Not executed in Controlled Publisher v1.",
)

WECHAT_ROLLBACK = ChannelRollbackCapability(
    channel="wechat",
    rollback_supported=False,
    strategy="manual_ops",
    notes="Published WeChat articles are not fully reversible via API; do not assume symmetric rollback.",
)


@dataclass
class RecoveryPlan:
    transaction_id: str
    overall_state: str
    retry_channels: list[str] = field(default_factory=list)
    skip_channels: list[str] = field(default_factory=list)
    rollback: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "overall_state": self.overall_state,
            "retry_channels": list(self.retry_channels),
            "skip_channels": list(self.skip_channels),
            "rollback": list(self.rollback),
            "notes": list(self.notes),
        }


def build_recovery_plan(txn: PublishTransaction) -> RecoveryPlan:
    retry: list[str] = []
    skip: list[str] = []
    rollback: list[dict] = []
    notes: list[str] = []

    for name, state, capability in (
        ("website", txn.website, WEBSITE_ROLLBACK),
        ("wechat", txn.wechat, WECHAT_ROLLBACK),
    ):
        if state.state is ChannelPublishState.SUCCEEDED:
            skip.append(name)
            notes.append(f"{name}: already SUCCEEDED — do not republish")
        elif state.state in (
            ChannelPublishState.FAILED,
            ChannelPublishState.VERIFICATION_FAILED,
            ChannelPublishState.NOT_STARTED,
            ChannelPublishState.PREPARED,
            ChannelPublishState.IN_PROGRESS,
        ):
            retry.append(name)
        if state.state is ChannelPublishState.SUCCEEDED and capability.rollback_supported:
            rollback.append({**capability.to_dict(), "action": "optional_if_full_abort"})
        elif state.state is ChannelPublishState.SUCCEEDED and not capability.rollback_supported:
            notes.append(f"{name}: rollback_supported=false — recovery is ops/manual")

    return RecoveryPlan(
        transaction_id=txn.transaction_id,
        overall_state=txn.overall_state.value,
        retry_channels=retry,
        skip_channels=skip,
        rollback=rollback,
        notes=notes,
    )
