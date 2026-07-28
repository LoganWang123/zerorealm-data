"""Deterministic ZeroRealm prompts for generated publishing media."""

from __future__ import annotations

from dataclasses import dataclass

from publishing.article import Article


DAILY_PROMPT_VERSION = "daily-v1"
HOMEPAGE_PROMPT_VERSION = "homepage-v1"

BRAND_STYLE = (
    "ZeroRealm AI 品牌视觉：深海军蓝、克制的科技蓝和少量翡翠绿，"
    "可信、清晰、现代、适合商业决策者；不使用霓虹渐变、发光字、"
    "卡通人物、水印或无法辨认的文字。"
)


@dataclass(frozen=True)
class PromptSet:
    cover: str
    body_images: list[str]
    video: str
    version: str


def build_daily_prompts(article: Article, body_image_count: int = 3) -> PromptSet:
    """Build one stable set of role-specific daily prompts."""
    context = "；".join(article.summary[:3])
    common = f"{BRAND_STYLE} 主题：{article.title}。核心内容：{context}。"
    roles = [
        "开篇配图：用清晰的零售场景和数据感建立当天主题，不出现标题文字。",
        "核心分析配图：表现产业链、经营数据和 AI 决策之间的关系。",
        "决策配图：表现趋势判断、行动路径与管理者决策，不使用复杂文字。",
    ]
    if body_image_count > len(roles):
        roles.extend(
            f"正文配图 {index}：围绕当天主题补充一个独立、可解释的商业场景。"
            for index in range(len(roles) + 1, body_image_count + 1)
        )

    return PromptSet(
        cover=(
            f"{common} 公众号封面，超宽横构图，主体居中偏右，"
            "左侧保留安全留白，不渲染任何文字。"
        ),
        body_images=[f"{common} {role} 16:9 横构图。" for role in roles[:body_image_count]],
        video=(
            f"{common} 生成一条约 15 秒的 9:16 竖屏短视频，"
            "用 3 个连贯镜头表现信号发现、分析和决策，镜头稳定，"
            "不渲染字幕或品牌文字，结尾留出品牌片尾空间。"
        ),
        version=DAILY_PROMPT_VERSION,
    )


def build_homepage_prompts() -> PromptSet:
    """Build the fixed homepage visual and video prompts."""
    common = (
        f"{BRAND_STYLE} 展现 AI 将分散的零售行业信号转化为结构化知识和决策洞察。"
    )
    return PromptSet(
        cover=(
            f"{common} 官网 Hero 主视觉，16:9 横构图，抽象数据网络与真实零售空间融合，"
            "右侧主体、左侧留白，不渲染文字。"
        ),
        body_images=[],
        video=(
            f"{common} 官网展示视频，16:9，约 15 秒，三个克制的电影感镜头，"
            "不出现字幕，不自动暗示循环。"
        ),
        version=HOMEPAGE_PROMPT_VERSION,
    )
