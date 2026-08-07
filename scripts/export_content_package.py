"""Export a multi-channel content package. Media: approved local only or pending brief."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publishing.media_generation.prompt_package import (
    build_brief_for_article,
    write_prompt_package,
)


FORBIDDEN_MEDIA_MARKERS = ("agnes", "agnes-image", "apihub.agnes")


def export_package(
    *,
    slug: str,
    title: str,
    body: str,
    channel_notes: dict | None = None,
    approved_media_dir: Path | None = None,
    out_root: Path = Path("dist/content-package"),
) -> Path:
    package = out_root / slug
    if package.exists():
        shutil.rmtree(package)
    for name in ("website", "wechat", "zhihu", "media", "sources"):
        (package / name).mkdir(parents=True, exist_ok=True)

    (package / "website" / "article.md").write_text(
        f"# {title}\n\n{body}\n", encoding="utf-8"
    )
    (package / "wechat" / "draft.md").write_text(
        f"# {title}\n\n{body}\n", encoding="utf-8"
    )
    (package / "zhihu" / "package.json").write_text(
        json.dumps(
            {
                "title": title,
                "body": body,
                "excerpt": body[:120],
                "topics": ["智能零售", "智能柜"],
                "sources": [],
                "coverPrompt": "pending_local_generation",
                "autoPublish": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    media_meta = {"assets": [], "policy": "approved-local-or-pending-brief", "agnes": False}
    if approved_media_dir and approved_media_dir.is_dir():
        for path in approved_media_dir.iterdir():
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                # Refuse copying anything that looks Agnes-tagged in filename
                if any(marker in path.name.lower() for marker in FORBIDDEN_MEDIA_MARKERS):
                    continue
                target = package / "media" / path.name
                shutil.copy2(path, target)
                media_meta["assets"].append(path.name)
    if not media_meta["assets"]:
        job = write_prompt_package(
            build_brief_for_article(
                content_id=slug,
                channel="wechat",
                purpose="cover",
                title=title,
                width=900,
                height=383,
                aspect_ratio="900:383",
            ),
            package / "media" / "pending",
        )
        media_meta["pendingJob"] = str(job.relative_to(package))

    metadata = {
        "slug": slug,
        "title": title,
        "channels": channel_notes or {"website": True, "wechat": "draft-only", "zhihu": "export-only"},
        "media": media_meta,
        "agnesImageGeneration": False,
    }
    (package / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (package / "sources" / "README.md").write_text(
        "Place public source citations here.\n", encoding="utf-8"
    )
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--approved-media", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist/content-package"))
    args = parser.parse_args()
    body = args.body
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8")
    path = export_package(
        slug=args.slug,
        title=args.title,
        body=body,
        approved_media_dir=args.approved_media,
        out_root=args.output,
    )
    print(json.dumps({"package": str(path), "agnes": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
