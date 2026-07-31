import hashlib
import json

import pytest

from publishing.media_generation.review import approve_media_manifest


def test_approve_media_manifest_binds_review_to_exact_file_hash(tmp_path):
    image = tmp_path / "cover.png"
    image.write_bytes(b"reviewed image")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    manifest_path = tmp_path / "media-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "assets": {
                    "cover": {
                        "role": "cover",
                        "local_path": str(image),
                        "sha256": digest,
                        "visual_reviewed": False,
                        "text_free": False,
                        "scene_relevant": False,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    approve_media_manifest(manifest_path, {"cover": digest})

    asset = json.loads(manifest_path.read_text(encoding="utf-8"))["assets"]["cover"]
    assert asset["visual_reviewed"] is True
    assert asset["text_free"] is True
    assert asset["scene_relevant"] is True
    assert asset["reviewed_sha256"] == digest


def test_approve_media_manifest_rejects_changed_or_unlisted_files(tmp_path):
    image = tmp_path / "cover.png"
    image.write_bytes(b"current")
    current_digest = hashlib.sha256(image.read_bytes()).hexdigest()
    manifest_path = tmp_path / "media-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "assets": {
                    "cover": {
                        "role": "cover",
                        "local_path": str(image),
                        "sha256": current_digest,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hash does not match"):
        approve_media_manifest(manifest_path, {"cover": "0" * 64})
    with pytest.raises(ValueError, match="exactly"):
        approve_media_manifest(manifest_path, {})
