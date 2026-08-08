"""Website controlled publisher adapter — fake/local backend only in v1."""

from __future__ import annotations

from dataclasses import dataclass, field

from content.controlled_publish.errors import (
    CONTENT_ALREADY_EXISTS,
    CONTENT_TYPE_MISMATCH,
    NETWORK_FORBIDDEN,
    PUBLISH_DISABLED,
    REVISION_CONFLICT,
    ControlledPublishError,
)
from content.controlled_publish.modes import ExecutionMode, publish_disabled
from content.controlled_publish.receipt import PublishReceipt, mock_website_receipt
from content.models import ContentType
from content.publisher_preflight import build_website_publish_plan, website_target_route
from content.release_candidate import ReleaseCandidate, assert_ready_for_publish


@dataclass
class WebsiteExistingContent:
    content_id: str
    revision: str
    fingerprint: str
    published: bool = True


@dataclass
class FakeGitBackend:
    """Records planned writes; never pushes or merges production."""

    existing: dict[str, WebsiteExistingContent] = field(default_factory=dict)
    patches: list[dict] = field(default_factory=list)
    pushes: int = 0
    network_calls: list = field(default_factory=list)

    def lookup(self, content_id: str) -> WebsiteExistingContent | None:
        return self.existing.get(content_id)

    def apply_create(self, patch: dict) -> dict:
        self.patches.append(dict(patch))
        cid = patch["content_id"]
        self.existing[cid] = WebsiteExistingContent(
            content_id=cid,
            revision=patch["revision"],
            fingerprint=patch["fingerprint"],
            published=True,
        )
        return {"ok": True, "commit_sha": "mock://git/commit/test-fake-sha", "patch": patch}


class WebsiteControlledPublisher:
    channel = "website"
    rollback_supported = True

    def __init__(self, backend: FakeGitBackend | None = None):
        self.backend = backend or FakeGitBackend()

    def content_path(self, rc: ReleaseCandidate) -> str:
        if rc.content_type in (ContentType.INSIGHT.value, "insight"):
            return f"content/insight/{rc.slug}.mdx"
        if rc.content_type in (ContentType.DAILY.value, "daily"):
            return f"content/daily/{rc.slug}.mdx"
        raise ControlledPublishError(CONTENT_TYPE_MISMATCH, f"Unknown content_type={rc.content_type}")

    def prepare(self, rc: ReleaseCandidate) -> dict:
        assert_ready_for_publish(rc)
        plan = build_website_publish_plan(rc)
        path = self.content_path(rc)
        route = website_target_route(rc)
        if rc.content_type == "insight" and path.startswith("content/daily/"):
            raise ControlledPublishError(CONTENT_TYPE_MISMATCH, "Insight must not write Daily path")
        prepared = {
            **plan,
            "target_repo": "zerorealm-website",
            "target_branch": "main",
            "content_path": path,
            "expected_route": route,
            "expected_title": (rc.website_artifact or {}).get("title") or rc.slug,
            "expected_content_id": rc.content_id,
            "expected_content_type": rc.content_type,
            "expected_fingerprint": rc.content_fingerprint,
            "create_only": True,
        }
        return prepared

    def preflight(self, rc: ReleaseCandidate, prepared: dict | None = None) -> dict:
        prepared = prepared or self.prepare(rc)
        existing = self.backend.lookup(rc.content_id)
        if existing and existing.published:
            if existing.revision != rc.revision or existing.fingerprint != rc.content_fingerprint:
                raise ControlledPublishError(
                    REVISION_CONFLICT if existing.revision != rc.revision else CONTENT_ALREADY_EXISTS,
                    f"Existing content_id={rc.content_id} revision={existing.revision}",
                )
            raise ControlledPublishError(
                CONTENT_ALREADY_EXISTS,
                f"content_id already published: {rc.content_id}",
            )
        return {"ok": True, "prepared": prepared, "create_only": True}

    def execute(
        self,
        rc: ReleaseCandidate,
        *,
        mode: ExecutionMode,
        prepared: dict | None = None,
        env: dict[str, str] | None = None,
    ) -> PublishReceipt:
        if publish_disabled(env):
            raise ControlledPublishError(PUBLISH_DISABLED, "PUBLISH_DISABLED=true blocks execute")
        if mode is ExecutionMode.DRY_RUN:
            raise ControlledPublishError(NETWORK_FORBIDDEN, "DRY_RUN cannot execute")
        # STAGING/PRODUCTION still require kill switch off — and v1 only allows fake backend.
        prepared = prepared or self.prepare(rc)
        self.preflight(rc, prepared)
        if self.backend.network_calls:
            raise ControlledPublishError(NETWORK_FORBIDDEN, "Network calls forbidden in v1 backend")
        patch = {
            "content_id": rc.content_id,
            "content_type": rc.content_type,
            "slug": rc.slug,
            "revision": rc.revision,
            "fingerprint": rc.content_fingerprint,
            "content_path": prepared["content_path"],
            "expected_route": prepared["expected_route"],
            "artifact_hash": prepared["artifact_hash"],
        }
        self.backend.apply_create(patch)
        return mock_website_receipt(
            release_candidate_id=rc.release_candidate_id,
            content_id=rc.content_id,
            revision=rc.revision,
            artifact_hash=prepared["artifact_hash"],
            fingerprint=rc.content_fingerprint,
            route=prepared["expected_route"],
            content_path=prepared["content_path"],
        )

    def receipt(self, receipt: PublishReceipt) -> dict:
        return receipt.to_dict()
