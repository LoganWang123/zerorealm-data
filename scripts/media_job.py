"""CLI for MediaJob workflow (IDE-native generation, not runtime providers)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publishing.media_generation.media_job import (
    JOBS_ROOT,
    attach_image,
    can_publish,
    create_job,
    list_jobs,
    load_job,
    set_review_status,
    validate_asset,
    write_job_package,
)


PURPOSE_SIZES = {
    "cover": (900, 383, "900:383"),
    "illustration": (1280, 720, "16:9"),
    "og": (1200, 630, "1.91:1"),
    "infographic": (1280, 720, "16:9"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("content_id")
    create.add_argument("--channel", default="website")
    create.add_argument("--purpose", choices=sorted(PURPOSE_SIZES), default="illustration")
    create.add_argument("--title", default="")
    create.add_argument("--content-type", default="research_or_daily")

    sub.add_parser("list").add_argument("--pending", action="store_true")
    show = sub.add_parser("show")
    show.add_argument("job_id")

    attach = sub.add_parser("attach")
    attach.add_argument("job_id")
    attach.add_argument("image_path", type=Path)
    attach.add_argument("--generator-agent", default="cursor")
    attach.add_argument("--generator-type", default="ide_native")

    validate = sub.add_parser("validate")
    validate.add_argument("job_id")

    status = sub.add_parser("status")
    status.add_argument("job_id")

    review = sub.add_parser("review")
    review.add_argument("job_id")
    review.add_argument("--approve", action="store_true")
    review.add_argument("--reject", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "create":
        width, height, ratio = PURPOSE_SIZES[args.purpose]
        job = create_job(
            content_id=args.content_id,
            content_type=args.content_type,
            channel=args.channel,
            purpose=args.purpose,
            title=args.title,
            width=width,
            height=height,
            aspect_ratio=ratio,
        )
        print(json.dumps(job.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "list":
        jobs = list_jobs(status="pending_generation" if args.pending else None)
        print(
            json.dumps(
                [{"id": j.id, "contentId": j.contentId, "status": j.status, "purpose": j.purpose} for j in jobs],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "show":
        job = load_job(args.job_id)
        print(json.dumps(job.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "attach":
        job = attach_image(
            args.job_id,
            args.image_path,
            generator_agent=args.generator_agent,
            generator_type=args.generator_type,
        )
        print(json.dumps(job.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        job = load_job(args.job_id)
        if not job.assetPath:
            print(json.dumps({"ok": False, "errors": ["no_asset"]}, ensure_ascii=False, indent=2))
            return 1
        report = validate_asset(Path(job.assetPath), width=job.width, height=job.height)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.command == "status":
        job = load_job(args.job_id)
        print(
            json.dumps(
                {
                    "id": job.id,
                    "status": job.status,
                    "reviewStatus": job.reviewStatus,
                    "validationStatus": job.validationStatus,
                    "canPublish": can_publish(job),
                    "generatorAgent": job.generatorAgent,
                    "sha256": job.sha256[:16] + "..." if job.sha256 else "",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "review":
        if args.approve == args.reject:
            print("specify exactly one of --approve / --reject", file=sys.stderr)
            return 2
        job = set_review_status(args.job_id, "approved" if args.approve else "rejected")
        print(json.dumps(job.to_dict(), ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
