"""Write local image prompt packages when generation is unavailable."""

from __future__ import annotations

import json
from pathlib import Path

from publishing.media_generation.image_brief import ImageBrief

DEFAULT_NEGATIVE = (
    "generic futuristic AI, robot hand, neon brain, cyberpunk city, "
    "fake dashboards, fake data, random Chinese text, watermark, "
    "invented brand logo, glowing chip, sci-fi poster"
)

DEFAULT_VISUAL_EN = (
    "editorial business photography, retail operations, smart cabinet in a "
    "convenience or office setting, urban fulfillment, natural lighting, "
    "documentary realism, premium business magazine, minimal, restrained, "
    "no text overlays, no logos"
)


def build_brief_for_article(
    *,
    content_id: str,
    channel: str,
    purpose: str,
    title: str,
    width: int,
    height: int,
    aspect_ratio: str,
) -> ImageBrief:
    subject = f"ZeroRealm research visual for: {title}"
    prompt_zh = (
        f"为「{title}」生成克制的商业研究配图。"
        f"场景围绕智能柜、便利零售或即时零售履约。"
        f"专业、真实、无科幻机器人、无霓虹科技风、画面内不写中文。"
    )
    prompt_en = f"{subject}. {DEFAULT_VISUAL_EN}"
    return ImageBrief(
        content_id=content_id,
        channel=channel,
        purpose=purpose,
        subject=subject,
        aspect_ratio=aspect_ratio,
        width=width,
        height=height,
        must_include=["smart retail terminal context", "realistic lighting"],
        text_overlay={},
        status="pending_local_generation",
        prompt_zh=prompt_zh,
        prompt_en=prompt_en,
        negative_prompt=DEFAULT_NEGATIVE,
    )


def write_prompt_package(brief: ImageBrief, root: str | Path = "dist/media-jobs") -> Path:
    """Write image-brief + prompts under dist/media-jobs/<content-slug>/."""
    slug = brief.content_id.replace("/", "-").replace("\\", "-")
    job_dir = Path(root) / f"{slug}-{brief.purpose}"
    job_dir.mkdir(parents=True, exist_ok=True)

    (job_dir / "image-brief.json").write_text(
        json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (job_dir / "prompt.zh-CN.txt").write_text(brief.prompt_zh + "\n", encoding="utf-8")
    (job_dir / "prompt.en.txt").write_text(brief.prompt_en + "\n", encoding="utf-8")
    (job_dir / "negative-prompt.txt").write_text(
        brief.negative_prompt + "\n", encoding="utf-8"
    )
    metadata = {
        "contentId": brief.content_id,
        "contentType": "research_or_daily",
        "channel": brief.channel,
        "purpose": brief.purpose,
        "aspectRatio": brief.aspect_ratio,
        "targetWidth": brief.width,
        "targetHeight": brief.height,
        "status": "pending_local_generation",
    }
    (job_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return job_dir
