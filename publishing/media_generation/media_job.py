"""MediaJob — IDE-assisted content production jobs (not a runtime provider).

IDE Agents (Cursor/Codex/etc.) generate image files offline, then attach them.
Never call Agnes. Never call Cursor/Codex APIs from Python.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from publishing.media_generation.asset_checks import inspect_image_file
from publishing.media_generation.prompt_package import DEFAULT_NEGATIVE, DEFAULT_VISUAL_EN

JOBS_ROOT = Path("dist/media-jobs")
GENERATED_ROOT = Path("output/media/generated")
APPROVED_ROOT = Path("output/media/approved")

ALLOWED_STATUSES = (
    "pending_generation",
    "generated",
    "validation_failed",
    "pending_review",
    "approved",
    "rejected",
)

SAFE_NAME = re.compile(r"^[A-Za-z0-9._\-]+$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class MediaJob:
    id: str
    contentId: str
    contentType: str
    channel: str
    purpose: str
    aspectRatio: str
    width: int
    height: int
    visualDirection: str = DEFAULT_VISUAL_EN
    promptZh: str = ""
    promptEn: str = ""
    negativePrompt: str = DEFAULT_NEGATIVE
    textOverlay: dict[str, str] = field(default_factory=dict)
    sourceIds: list[str] = field(default_factory=list)
    generationMode: str = "ide-native"
    generatorType: str = ""  # ide_native|programmatic|manual|legacy
    generatorAgent: str = ""  # cursor|codex|other|manual — provenance only
    preferredAgent: str = "current"
    assetPath: str = ""
    sha256: str = ""
    validationStatus: str = "pending"
    reviewStatus: str = "pending_generation"
    status: str = "pending_generation"
    createdAt: str = ""
    generatedAt: str = ""
    reviewedAt: str = ""
    title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MediaJob:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {key: value for key, value in data.items() if key in known}
        return cls(**filtered)


def job_dir(job: MediaJob, root: Path = JOBS_ROOT) -> Path:
    return root / job.contentId / job.id


def write_job_package(job: MediaJob, root: Path = JOBS_ROOT) -> Path:
    directory = job_dir(job, root)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "image-brief.json").write_text(
        json.dumps(
            {
                "content_id": job.contentId,
                "channel": job.channel,
                "purpose": job.purpose,
                "aspect_ratio": job.aspectRatio,
                "width": job.width,
                "height": job.height,
                "visual_direction": job.visualDirection,
                "prompt_zh": job.promptZh,
                "prompt_en": job.promptEn,
                "negative_prompt": job.negativePrompt,
                "text_overlay": job.textOverlay,
                "status": job.status,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (directory / "prompt.zh-CN.txt").write_text(job.promptZh + "\n", encoding="utf-8")
    (directory / "prompt.en.txt").write_text(job.promptEn + "\n", encoding="utf-8")
    (directory / "negative-prompt.txt").write_text(
        job.negativePrompt + "\n", encoding="utf-8"
    )
    metadata = {
        "contentId": job.contentId,
        "contentType": job.contentType,
        "channel": job.channel,
        "purpose": job.purpose,
        "aspectRatio": job.aspectRatio,
        "targetWidth": job.width,
        "targetHeight": job.height,
        "generationMode": job.generationMode,
        "preferredAgent": job.preferredAgent,
        "status": job.status,
        "generatorType": job.generatorType,
        "generatorAgent": job.generatorAgent,
        "assetPath": job.assetPath,
        "sha256": job.sha256,
        "validationStatus": job.validationStatus,
        "reviewStatus": job.reviewStatus,
    }
    (directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (directory / "job.json").write_text(
        json.dumps(job.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return directory


def create_job(
    *,
    content_id: str,
    content_type: str = "research_or_daily",
    channel: str = "website",
    purpose: str = "cover",
    title: str = "",
    width: int = 1280,
    height: int = 720,
    aspect_ratio: str = "16:9",
    root: Path = JOBS_ROOT,
) -> MediaJob:
    job_id = f"mj-{uuid.uuid4().hex[:12]}"
    subject = title or content_id
    prompt_zh = (
        f"为「{subject}」生成克制的商业研究场景图。"
        f"智能柜/即时零售/便利零售真实环境，自然光，纪录片摄影感。"
        f"画面内不要中文、不要 Logo、不要虚假数据仪表盘。"
    )
    prompt_en = (
        f"Editorial business photography for ZeroRealm research: {subject}. "
        f"{DEFAULT_VISUAL_EN}"
    )
    job = MediaJob(
        id=job_id,
        contentId=content_id,
        contentType=content_type,
        channel=channel,
        purpose=purpose,
        aspectRatio=aspect_ratio,
        width=width,
        height=height,
        promptZh=prompt_zh,
        promptEn=prompt_en,
        textOverlay={},
        status="pending_generation",
        reviewStatus="pending_generation",
        createdAt=_now(),
        title=title,
    )
    write_job_package(job, root)
    return job


def load_job(job_id: str, root: Path = JOBS_ROOT) -> MediaJob:
    matches = list(root.glob(f"*/{job_id}/job.json"))
    if not matches:
        raise FileNotFoundError(f"MediaJob not found: {job_id}")
    return MediaJob.from_dict(json.loads(matches[0].read_text(encoding="utf-8")))


def list_jobs(root: Path = JOBS_ROOT, *, status: str | None = None) -> list[MediaJob]:
    jobs: list[MediaJob] = []
    if not root.exists():
        return jobs
    for path in root.glob("*/**/job.json"):
        job = MediaJob.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if status and job.status != status:
            continue
        jobs.append(job)
    return sorted(jobs, key=lambda item: item.createdAt, reverse=True)


def _assert_safe_path(path: Path) -> None:
    name = path.name
    if not SAFE_NAME.match(name):
        raise ValueError(f"unsafe filename: {name}")
    resolved = path.resolve()
    if ".." in path.parts:
        raise ValueError("unsafe path")
    # Block absolute paths outside cwd when relative expected — still allow absolute inputs
    if not resolved.exists():
        raise FileNotFoundError(str(path))


def validate_asset(path: Path, *, width: int, height: int) -> dict:
    _assert_safe_path(path)
    report = inspect_image_file(path)
    errors = list(report.get("errors") or [])
    if report.get("corrupted"):
        errors.append("corrupted")
    if not report.get("exists"):
        errors.append("missing")
    if report.get("width") and report.get("height"):
        # Allow 5% tolerance
        if abs(report["width"] - width) > max(8, width * 0.05) or abs(
            report["height"] - height
        ) > max(8, height * 0.05):
            errors.append(
                f"dimension_mismatch expected={width}x{height} got={report['width']}x{report['height']}"
            )
    if report.get("sizeBytes", 0) and report["sizeBytes"] > 12_000_000:
        errors.append("oversized")
    if report.get("sizeBytes", 0) and report["sizeBytes"] < 1024:
        errors.append("too_small")
    report["ok"] = not errors
    report["errors"] = errors
    return report


def attach_image(
    job_id: str,
    image_path: Path | str,
    *,
    generator_type: str = "ide_native",
    generator_agent: str = "cursor",
    root: Path = JOBS_ROOT,
    auto_approve: bool = False,
) -> MediaJob:
    """Copy IDE-generated image into the job, validate, mark pending_review.

    Publishing eligibility depends on reviewStatus/hash only — never on generatorAgent.
    """
    if auto_approve:
        raise ValueError("auto_approve is forbidden; human review required")
    job = load_job(job_id, root)
    source = Path(image_path)
    _assert_safe_path(source)
    inspection = validate_asset(source, width=job.width, height=job.height)
    if not inspection["ok"]:
        job.status = "validation_failed"
        job.validationStatus = "failed"
        job.reviewStatus = "validation_failed"
        write_job_package(job, root)
        raise ValueError(f"validation failed: {inspection['errors']}")

    dest_dir = GENERATED_ROOT / job.contentId / job.id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{job.purpose}{source.suffix.lower() or '.png'}"
    shutil.copy2(source, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()

    job.assetPath = str(dest).replace("\\", "/")
    job.sha256 = digest
    job.generatorType = generator_type
    job.generatorAgent = generator_agent
    job.generatedAt = _now()
    job.status = "pending_review"
    job.validationStatus = "passed"
    job.reviewStatus = "pending_review"
    write_job_package(job, root)
    # Also mirror into job folder for operators
    shutil.copy2(dest, job_dir(job, root) / dest.name)
    return job


def set_review_status(job_id: str, status: str, *, root: Path = JOBS_ROOT) -> MediaJob:
    if status not in {"approved", "rejected", "pending_review"}:
        raise ValueError(f"unsupported review status: {status}")
    job = load_job(job_id, root)
    if status == "approved" and job.validationStatus != "passed":
        raise ValueError("cannot approve job that failed validation")
    if status == "approved" and not job.sha256:
        raise ValueError("cannot approve job without sha256")
    job.reviewStatus = status
    job.status = status
    job.reviewedAt = _now()
    if status == "approved" and job.assetPath:
        approved_dir = APPROVED_ROOT / job.contentId
        approved_dir.mkdir(parents=True, exist_ok=True)
        src = Path(job.assetPath)
        if src.is_file():
            target = approved_dir / src.name
            shutil.copy2(src, target)
            job.assetPath = str(target).replace("\\", "/")
    write_job_package(job, root)
    return job


def can_publish(job: MediaJob) -> bool:
    """Release gate ignores generatorAgent; only validation + approval matter."""
    return (
        job.reviewStatus == "approved"
        and job.validationStatus == "passed"
        and bool(job.sha256)
        and bool(job.assetPath)
        and Path(job.assetPath).is_file()
    )
