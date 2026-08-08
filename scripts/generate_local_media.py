"""Generate local media or write prompt packages. Never calls Agnes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publishing.media_generation.errors import LocalImageGeneratorUnavailable
from publishing.media_generation.prompt_package import (
    build_brief_for_article,
    write_prompt_package,
)
from publishing.media_generation.providers import LocalImageGenerator
from publishing.media_generation.asset_checks import inspect_image_file


PURPOSE_SPECS = {
    "cover": ("900x383", 900, 383, "900:383"),
    "illustration": ("1280x720", 1280, 720, "16:9"),
    "og": ("1200x630", 1200, 630, "1.91:1"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_id")
    parser.add_argument("--channel", choices=["website", "wechat", "zhihu"], default="website")
    parser.add_argument("--purpose", choices=sorted(PURPOSE_SPECS), default="cover")
    parser.add_argument("--title", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prompt-only", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("output/media/generated"))
    parser.add_argument("--jobs-root", type=Path, default=Path("dist/media-jobs"))
    args = parser.parse_args(argv)

    size, width, height, ratio = PURPOSE_SPECS[args.purpose]
    title = args.title or args.content_id
    brief = build_brief_for_article(
        content_id=args.content_id,
        channel=args.channel,
        purpose=args.purpose,
        title=title,
        width=width,
        height=height,
        aspect_ratio=ratio,
    )

    if args.prompt_only or args.dry_run:
        job_dir = write_prompt_package(brief, args.jobs_root)
        print(
            json.dumps(
                {
                    "status": "pending_local_generation",
                    "jobDir": str(job_dir),
                    "code": "LOCAL_IMAGE_GENERATOR_UNAVAILABLE"
                    if args.prompt_only
                    else "DRY_RUN",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    generator = LocalImageGenerator(allow_programmatic=True)
    if not generator.available:
        job_dir = write_prompt_package(brief, args.jobs_root)
        print(
            json.dumps(
                {
                    "status": "pending_local_generation",
                    "code": "LOCAL_IMAGE_GENERATOR_UNAVAILABLE",
                    "jobDir": str(job_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    try:
        content = generator.generate_image(brief.prompt_en or title, size)
    except LocalImageGeneratorUnavailable:
        job_dir = write_prompt_package(brief, args.jobs_root)
        print(
            json.dumps(
                {
                    "status": "pending_local_generation",
                    "code": "LOCAL_IMAGE_GENERATOR_UNAVAILABLE",
                    "jobDir": str(job_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    out_dir = args.output_root / args.content_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.purpose}.png"
    temporary = out_path.with_suffix(".png.partial")
    temporary.write_bytes(content)
    temporary.replace(out_path)
    report = inspect_image_file(out_path)
    print(
        json.dumps(
            {
                "status": "generated",
                "path": str(out_path),
                "inspection": report,
                "reviewStatus": "pending_review",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
