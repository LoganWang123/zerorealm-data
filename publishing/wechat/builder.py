"""微信渠道 Builder 注册.

通过 @PublisherRegistry.register("wechat") 注册到全局注册表。
"""

from __future__ import annotations

import os

from publishing.factory import BuilderContext
from publishing.media_storage import LocalMediaStorage
from publishing.models import ChannelTarget
from publishing.registry import PublisherRegistry
from publishing.wechat.client import WechatClient
from publishing.wechat.publisher import WechatPublisher
from publishing.wechat.renderer import WechatRenderer


@PublisherRegistry.register("wechat")
class WechatChannelBuilder:
    """微信公众号渠道 Builder."""

    @staticmethod
    def build(ctx: BuilderContext) -> ChannelTarget:
        """组装微信渠道 ChannelTarget."""
        # 从环境变量读取 secrets
        app_id = ctx.config.wechat.app_id or os.getenv("WECHAT_APPID", "")
        app_secret = ctx.config.wechat.app_secret or os.getenv("WECHAT_SECRET", "")

        client = WechatClient(app_id, app_secret)
        storage = LocalMediaStorage()  # dry-run 用本地存储，正式环境替换为 WechatMediaStorage
        renderer = WechatRenderer(storage)
        publisher = WechatPublisher(client, manifest=ctx.manifest)

        return ChannelTarget(name="wechat", renderer=renderer, publisher=publisher)
