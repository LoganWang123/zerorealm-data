"""Generate complete daily media bundles with resumable manifests."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from publishing.media_generation.manifest import MediaManifestRepository
from publishing.media_generation.prompts import PromptSet, build_daily_prompts
from publishing.models import MediaAsset, MediaBundle

if TYPE_CHECKING:
    from publishing.article import Article
    from publishing.config import MediaConfig
    from publishing.media_generation.client import AgnesClient


class MediaGenerationService:
    """Create or safely reuse the required daily media set."""

    def __init__(
        self,
        client: AgnesClient,
        config: MediaConfig,
        output_root: str | Path = "assets/generated",
        prompt_builder: Callable[[Article, int], PromptSet] = build_daily_prompts,
    ):
        self._client = client
        self._config = config
        self._output_root = Path(output_root)
        self._prompt_builder = prompt_builder

    def generate_daily(self, article: Article) -> MediaBundle:
        prompts = self._prompt_builder(article, self._config.body_image_count)
        directory = self._output_root / article.date
        directory.mkdir(parents=True, exist_ok=True)
        repository = MediaManifestRepository(directory / "media-manifest.json")
        manifest = self._prepare_manifest(repository.load(), article, prompts)

        cover = self._image_asset(
            repository,
            manifest,
            directory,
            role="cover",
            filename="cover.png",
            prompt=prompts.cover,
            size="900x383",
            width=900,
            height=383,
            prompt_version=prompts.version,
        )
        body_images = [
            self._image_asset(
                repository,
                manifest,
                directory,
                role=f"body_{index}",
                filename=f"body-{index}.png",
                prompt=prompt,
                size="1280x720",
                width=1280,
                height=720,
                prompt_version=prompts.version,
            )
            for index, prompt in enumerate(prompts.body_images, 1)
        ]
        video = (
            self._video_asset(
                repository,
                manifest,
                directory,
                prompt=prompts.video,
                prompt_version=prompts.version,
            )
            if self._config.video_enabled
            else None
        )
        manifest["complete"] = True
        repository.save(manifest)
        return MediaBundle(cover=cover, body_images=body_images, video=video)

    def _prepare_manifest(
        self,
        existing: dict,
        article: Article,
        prompts: PromptSet,
    ) -> dict:
        identity = {
            "article_uuid": article.metadata.uuid,
            "content_revision": article.metadata.content_revision,
            "prompt_version": prompts.version,
            "image_model": self._client.image_model,
            "video_model": self._client.video_model,
        }
        if all(existing.get(key) == value for key, value in identity.items()):
            manifest = dict(existing)
            manifest.setdefault("assets", {})
            return manifest
        return {**identity, "complete": False, "assets": {}}

    def _image_asset(
        self,
        repository: MediaManifestRepository,
        manifest: dict,
        directory: Path,
        *,
        role: str,
        filename: str,
        prompt: str,
        size: str,
        width: int,
        height: int,
        prompt_version: str,
    ) -> MediaAsset:
        reusable = self._reusable_asset(manifest, role)
        if reusable is not None:
            return reusable
        content = self._client.generate_image(prompt, size)
        asset = self._write_asset(
            directory / filename,
            content,
            role=role,
            mime="image/png",
            width=width,
            height=height,
            prompt_version=prompt_version,
            model=self._client.image_model,
        )
        self._record_asset(repository, manifest, asset)
        return asset

    def _video_asset(
        self,
        repository: MediaManifestRepository,
        manifest: dict,
        directory: Path,
        *,
        prompt: str,
        prompt_version: str,
    ) -> MediaAsset:
        role = "short_video"
        reusable = self._reusable_asset(manifest, role)
        if reusable is not None:
            return reusable
        content = self._client.generate_video(
            prompt=prompt,
            aspect_ratio=self._config.video_aspect_ratio,
            duration_seconds=self._config.video_duration_seconds,
            poll_interval_seconds=self._config.poll_interval_seconds,
            poll_timeout_seconds=self._config.poll_timeout_seconds,
        )
        asset = self._write_asset(
            directory / "short-video.mp4",
            content,
            role=role,
            mime="video/mp4",
            width=720,
            height=1280,
            duration_seconds=float(self._config.video_duration_seconds),
            prompt_version=prompt_version,
            model=self._client.video_model,
        )
        self._record_asset(repository, manifest, asset)
        return asset

    @staticmethod
    def _write_asset(
        path: Path,
        content: bytes,
        *,
        role: str,
        mime: str,
        width: int,
        height: int,
        prompt_version: str,
        model: str,
        duration_seconds: float = 0.0,
    ) -> MediaAsset:
        if not content:
            raise ValueError(f"{role} generation returned an empty file")
        temporary = path.with_suffix(path.suffix + ".partial")
        temporary.write_bytes(content)
        temporary.replace(path)
        return MediaAsset(
            role=role,
            local_path=str(path),
            mime=mime,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            sha256=hashlib.sha256(content).hexdigest(),
            prompt_version=prompt_version,
            model=model,
        )

    @staticmethod
    def _record_asset(
        repository: MediaManifestRepository,
        manifest: dict,
        asset: MediaAsset,
    ) -> None:
        manifest["complete"] = False
        manifest["assets"][asset.role] = asdict(asset)
        repository.save(manifest)

    @staticmethod
    def _reusable_asset(manifest: dict, role: str) -> MediaAsset | None:
        raw = manifest.get("assets", {}).get(role)
        if not isinstance(raw, dict):
            return None
        try:
            asset = MediaAsset(**raw)
        except TypeError:
            return None
        path = Path(asset.local_path)
        if not path.exists() or not path.is_file():
            return None
        content = path.read_bytes()
        if not content or hashlib.sha256(content).hexdigest() != asset.sha256:
            return None
        return asset
