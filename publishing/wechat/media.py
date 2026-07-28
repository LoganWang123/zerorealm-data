"""WeChat-specific media placeholder and video embed rendering."""

from __future__ import annotations

from html import escape


class WechatVideoEmbedder:
    """Keep channel-specific video markup out of the generic media model."""

    @staticmethod
    def render(media_id: str, title: str) -> str:
        if not media_id:
            raise ValueError("WeChat video media_id is required")
        safe_id = escape(media_id, quote=True)
        safe_title = escape(title, quote=True)
        return (
            '<iframe class="video_iframe rich_pages wx_video_iframe" '
            'frameborder="0" allowfullscreen="true" '
            f'data-media-id="{safe_id}" data-mpvid="{safe_id}" '
            f'title="{safe_title}"></iframe>'
        )
