"""Website channel Builder registration."""

from __future__ import annotations

from pathlib import Path

from publishing.factory import BuilderContext
from publishing.models import ChannelTarget
from publishing.registry import PublisherRegistry
from publishing.website.publisher import WebsitePublisher, default_website_daily_dir
from publishing.website.renderer import WebsiteRenderer


@PublisherRegistry.register("website")
class WebsiteChannelBuilder:
    """官网 Daily 渠道 Builder."""

    @staticmethod
    def build(ctx: BuilderContext) -> ChannelTarget:
        website_cfg = getattr(ctx.config, "website", None)
        content_dir = default_website_daily_dir()
        package_dir = Path("dist/content-package")
        if website_cfg is not None:
            if getattr(website_cfg, "content_dir", ""):
                content_dir = Path(website_cfg.content_dir)
            if getattr(website_cfg, "package_dir", ""):
                package_dir = Path(website_cfg.package_dir)

        renderer = WebsiteRenderer()
        publisher = WebsitePublisher(
            content_dir=content_dir,
            package_dir=package_dir,
            manifest=ctx.manifest,
        )
        return ChannelTarget(name="website", renderer=renderer, publisher=publisher)
