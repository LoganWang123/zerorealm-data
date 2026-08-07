"""Local image file inspection helpers."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from PIL import Image


def inspect_image_file(path: Path | str) -> dict:
    path = Path(path)
    report: dict = {
        "path": str(path),
        "exists": path.is_file(),
        "mime": None,
        "width": None,
        "height": None,
        "ratio": None,
        "sizeBytes": None,
        "sha256": None,
        "corrupted": False,
        "filenameOk": bool(path.name) and ".." not in path.name,
        "errors": [],
    }
    if not report["exists"]:
        report["errors"].append("missing")
        return report
    try:
        data = path.read_bytes()
    except OSError as exc:
        report["corrupted"] = True
        report["errors"].append(f"read_failed:{exc}")
        return report
    report["sizeBytes"] = len(data)
    report["sha256"] = hashlib.sha256(data).hexdigest()
    guess, _ = mimetypes.guess_type(path.name)
    report["mime"] = guess
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            report["width"] = width
            report["height"] = height
            report["ratio"] = round(width / height, 4) if height else None
            report["mime"] = Image.MIME.get(image.format or "", guess)
    except Exception as exc:  # noqa: BLE001 - surface corrupt files
        report["corrupted"] = True
        report["errors"].append(f"corrupt:{exc}")
    return report
