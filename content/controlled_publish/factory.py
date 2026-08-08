"""Controlled publisher factory — separate from legacy publishing.factory.PublisherFactory."""

from __future__ import annotations

from content.controlled_publish.wechat_adapter import FakeWeChatBackend, WeChatControlledPublisher
from content.controlled_publish.website_adapter import FakeGitBackend, WebsiteControlledPublisher


class ControlledPublisherFactory:
    """Builds channel adapters for Release Orchestrator publish path."""

    def __init__(
        self,
        *,
        website_backend: FakeGitBackend | None = None,
        wechat_backend: FakeWeChatBackend | None = None,
    ):
        self.website_backend = website_backend or FakeGitBackend()
        self.wechat_backend = wechat_backend or FakeWeChatBackend()

    def website(self) -> WebsiteControlledPublisher:
        return WebsiteControlledPublisher(self.website_backend)

    def wechat(self) -> WeChatControlledPublisher:
        return WeChatControlledPublisher(self.wechat_backend)

    def get(self, channel: str):
        if channel == "website":
            return self.website()
        if channel == "wechat":
            return self.wechat()
        raise ValueError(f"Unknown channel: {channel}")
