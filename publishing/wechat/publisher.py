"""WechatPublisher — 微信公众号发布器.

RenderResult → 微信 API → PublishResult。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from publishing.base import BasePublisher
from publishing.models import PublishResult, PublishStatus, WechatMetadata

if TYPE_CHECKING:
    from publishing.manifest_repository import ManifestRepository
    from publishing.models import RenderResult
    from publishing.wechat.client import WechatClient


class WechatPublisher(BasePublisher):
    """微信公众号发布器."""

    def __init__(self, client: WechatClient, manifest: ManifestRepository | None = None):
        self._client = client
        self._manifest = manifest

    def publish(self, result: RenderResult, dry_run: bool = False) -> PublishResult:
        """发布到微信公众号."""
        start = time.time()

        if dry_run:
            return PublishResult(
                status=PublishStatus.DRY_RUN,
                channel="wechat",
                message="Dry run: payload prepared, no API call",
                duration=time.time() - start,
            )

        # 上传封面
        cover_media_id = ""
        if result.cover.local_path:
            try:
                upload_resp = self._client.upload_permanent_image(result.cover.local_path)
                cover_media_id = upload_resp.get("media_id", "")
            except Exception as e:
                return PublishResult(
                    status=PublishStatus.FAILED,
                    channel="wechat",
                    message=f"Cover upload failed: {e}",
                    duration=time.time() - start,
                )

        # 构建草稿 payload
        metadata = result.channel_metadata
        digest = metadata.digest if isinstance(metadata, WechatMetadata) else result.summary

        article_payload = {
            "title": result.title,
            "author": result.author,
            "digest": digest,
            "content": result.body,
            "thumb_media_id": cover_media_id,
            "need_open_comment": 0,
        }

        # 幂等：检查 Manifest
        existing = None
        if self._manifest:
            existing = self._manifest.find(result.article_uuid, "wechat")

        try:
            if existing and existing.draft_id:
                # 更新已有草稿
                self._client.update_draft(existing.draft_id, 0, article_payload)
                status = PublishStatus.UPDATED
                draft_id = existing.draft_id
            else:
                # 新建草稿
                draft_id = self._client.create_draft([article_payload])
                status = PublishStatus.SUCCESS

            return PublishResult(
                status=status,
                channel="wechat",
                draft_id=draft_id,
                duration=time.time() - start,
                message=f"Draft {'updated' if status == PublishStatus.UPDATED else 'created'}",
            )
        except Exception as e:
            return PublishResult(
                status=PublishStatus.FAILED,
                channel="wechat",
                message=f"Publish failed: {e}",
                duration=time.time() - start,
            )
