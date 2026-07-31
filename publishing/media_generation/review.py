"""Bind a visual media approval to the exact reviewed files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from publishing.media_generation.manifest import MediaManifestRepository


def approve_media_manifest(
    manifest_path: str | Path,
    approved_hashes: dict[str, str],
) -> dict:
    repository = MediaManifestRepository(manifest_path)
    manifest = repository.load()
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise ValueError("media manifest has no assets")
    if set(approved_hashes) != set(assets):
        raise ValueError("approval must list exactly every manifest asset")

    for role, raw in assets.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{role} manifest entry is invalid")
        path = Path(str(raw.get("local_path", "")))
        if not path.is_file():
            raise ValueError(f"{role} file is missing")
        current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if approved_hashes[role].lower() != current_hash:
            raise ValueError(f"{role} approved hash does not match current file")
        if str(raw.get("sha256", "")).lower() != current_hash:
            raise ValueError(f"{role} manifest hash does not match current file")
        raw["visual_reviewed"] = True
        raw["text_free"] = True
        raw["scene_relevant"] = True
        raw["reviewed_sha256"] = current_hash

    repository.save(manifest)
    return manifest
