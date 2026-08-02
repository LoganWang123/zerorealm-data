"""WechatPublisher — 微信公众号发布器.

RenderResult → 微信 API → PublishResult。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from publishing.base import BasePublisher
from publishing.models import PublishResult, PublishStatus, WechatMetadata
from publishing.wechat.media import WechatVideoEmbedder

if TYPE_CHECKING:
    from publishing.manifest_repository import ManifestRepository
    from publishing.models import RenderResult
    from publishing.wechat.client import WechatClient


BRAND_FOOTER_MARKER = 'data-zr-brand-footer="true"'


def append_brand_footer(body: str) -> str:
    """Append the standard ZeroRealm AI contact footer exactly once."""
    if BRAND_FOOTER_MARKER in body:
        return body
    footer = (
        '<section data-zr-brand-footer="true" style="margin:32px 0 0;padding:20px 0 0;'
        'border-top:1px solid #e5e7eb;color:#4b5563;line-height:1.8;">'
        '<p style="margin:0 0 8px;font-size:16px;font-weight:bold;color:#111827;">'
        '关于 ZeroRealm AI</p>'
        '<p style="margin:0 0 12px;font-size:14px;">'
        'ZeroRealm AI 持续关注智能零售、无人零售与终端运营，提供每日经营信号、行业洞察与专题研究。'
        '</p>'
        '<p style="margin:0 0 4px;font-size:14px;">公开案例征集｜资料纠错｜行业合作</p>'
        '<p style="margin:0;font-size:14px;">邮箱：'
        '<a href="mailto:hi@zerorealm.tech" style="color:#2563eb;text-decoration:none;">'
        'hi@zerorealm.tech</a><br/>官网：'
        '<a href="https://zerorealm.tech" style="color:#2563eb;text-decoration:none;">'
        'https://zerorealm.tech</a></p>'
        '</section>'
    )
    return f"{body}\n{footer}"


class WechatPublisher(BasePublisher):
    """微信公众号发布器."""

    def __init__(self, client: WechatClient, manifest: ManifestRepository | None = None):
        self._client = client
        self._manifest = manifest

    def publish(
        self,
        result: RenderResult,
        dry_run: bool = False,
        publish_now: bool = False,
        notify_followers: bool = False,
    ) -> PublishResult:
        """发布到微信公众号."""
        start = time.time()

        if dry_run:
            return PublishResult(
                status=PublishStatus.DRY_RUN,
                channel="wechat",
                message="Dry run: payload prepared, no API call",
                duration=time.time() - start,
            )

        body = append_brand_footer(result.body)
        uploaded_image_urls: list[str] = []
        for media in result.media:
            token = f"zr-media://{media.role}"
            if token not in body:
                return PublishResult(
                    status=PublishStatus.FAILED,
                    channel="wechat",
                    message=f"Body image placeholder missing: {media.role}",
                    duration=time.time() - start,
                )
            try:
                remote_url = self._client.upload_content_image(media.local_path)
            except Exception as e:
                return PublishResult(
                    status=PublishStatus.FAILED,
                    channel="wechat",
                    message=f"Body image upload failed ({media.role}): {e}",
                    duration=time.time() - start,
                )
            uploaded_image_urls.append(remote_url)
            body = body.replace(token, remote_url)

        if result.video is not None:
            token = f"zr-video://{result.video.role}"
            if token not in body:
                return PublishResult(
                    status=PublishStatus.FAILED,
                    channel="wechat",
                    message="Video placeholder missing",
                    duration=time.time() - start,
                )
            try:
                upload_resp = self._client.upload_permanent_video(
                    result.video.local_path,
                    title=result.title[:64],
                    introduction=result.summary[:120],
                )
                body = body.replace(
                    token,
                    WechatVideoEmbedder.render(
                        upload_resp.get("media_id", ""),
                        result.title,
                    ),
                )
            except Exception as e:
                return PublishResult(
                    status=PublishStatus.FAILED,
                    channel="wechat",
                    message=f"Video upload failed: {e}",
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
        digest = _truncate_utf8(digest, 120)

        article_payload = {
            "title": result.title,
            "author": result.author,
            "digest": digest,
            "content": body,
            "thumb_media_id": cover_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 1,
        }

        # 幂等：检查 Manifest
        existing = None
        if self._manifest:
            existing = self._manifest.find(result.article_uuid, "wechat")

        try:
            if notify_followers and existing and existing.publish_id:
                return PublishResult(
                    status=PublishStatus.SKIPPED,
                    channel="wechat",
                    draft_id=existing.draft_id,
                    publish_id=existing.publish_id,
                    duration=time.time() - start,
                    message="Follower notification already sent",
                )

            if notify_followers:
                draft_id = self._client.create_mass_article([article_payload])
                status = PublishStatus.SUCCESS
            elif existing and existing.draft_id:
                # 更新已有草稿
                self._client.update_draft(existing.draft_id, 0, article_payload)
                status = PublishStatus.UPDATED
                draft_id = existing.draft_id
            else:
                # 新建草稿
                draft_id = self._client.create_draft([article_payload])
                status = PublishStatus.SUCCESS

            publish_id = None
            if notify_followers:
                publish_id = self._client.send_mass_article(draft_id)
            else:
                _verify_draft_readback(
                    self._client.get_draft(draft_id),
                    article_payload,
                    required_image_urls=uploaded_image_urls,
                )
                if publish_now:
                    publish_id = self._client.submit_publish(draft_id)

            return PublishResult(
                status=status,
                channel="wechat",
                draft_id=draft_id,
                publish_id=publish_id,
                duration=time.time() - start,
                message=(
                    "Follower notification sent"
                    if notify_followers
                    else (
                        f"Free publish submitted (draft {'updated' if status == PublishStatus.UPDATED else 'created'}; followers are not notified)"
                        if publish_now
                        else f"Draft {'updated' if status == PublishStatus.UPDATED else 'created'}"
                    )
                ),
            )
        except Exception as e:
            return PublishResult(
                status=PublishStatus.FAILED,
                channel="wechat",
                message=f"Publish failed: {e}",
                duration=time.time() - start,
            )


def _truncate_utf8(value: str, max_bytes: int) -> str:
    """Truncate text without splitting a UTF-8 code point."""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def _verify_draft_readback(
    response: dict,
    expected: dict,
    *,
    required_image_urls: list[str],
) -> None:
    """Fail closed when WeChat did not store the complete draft payload."""
    items = response.get("news_item") if isinstance(response, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise ValueError("Draft readback did not return an article")
    stored = items[0]
    if stored.get("title") != expected["title"]:
        raise ValueError("Draft readback title mismatch")
    if stored.get("thumb_media_id", "") != expected["thumb_media_id"]:
        raise ValueError("Draft readback cover mismatch")
    if stored.get("content_source_url"):
        raise ValueError("Draft readback unexpectedly contains a source URL")
    content = stored.get("content", "")
    required_fragments = [
        "hi@zerorealm.tech",
        "https://zerorealm.tech",
        *required_image_urls,
    ]
    missing = [fragment for fragment in required_fragments if fragment not in content]
    if missing:
        raise ValueError("Draft readback is missing required content")
