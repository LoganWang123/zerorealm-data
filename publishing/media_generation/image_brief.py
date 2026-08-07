"""Internal ImageBrief model — never exported to Public Bundle."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ImageBrief:
    content_id: str
    channel: str  # wechat|website|zhihu
    purpose: str  # cover|illustration|og
    subject: str = ""
    visual_direction: str = (
        "editorial business photography, retail operations, smart cabinet, "
        "restrained, documentary realism, premium business magazine"
    )
    aspect_ratio: str = "16:9"
    width: int = 1280
    height: int = 720
    must_include: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(
        default_factory=lambda: [
            "generic futuristic AI",
            "robot hand",
            "neon brain",
            "cyberpunk city",
            "fake dashboards",
            "fake data charts",
            "random Chinese text in image",
            "watermark",
            "invented brand logo",
        ]
    )
    text_overlay: dict[str, str] = field(default_factory=dict)
    data_source_ids: list[str] = field(default_factory=list)
    status: str = "draft"  # draft|pending_local_generation|generated|pending_review|approved|rejected
    prompt_zh: str = ""
    prompt_en: str = ""
    negative_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
