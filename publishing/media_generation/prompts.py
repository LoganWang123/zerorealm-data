"""Deterministic ZeroRealm prompts for generated publishing media."""

from __future__ import annotations

from dataclasses import dataclass

from publishing.article import Article


DAILY_PROMPT_VERSION = "daily-v1"
HOMEPAGE_PROMPT_VERSION = "homepage-v2"

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
    video_scenes: tuple[str, ...] = ()


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
        f"{BRAND_STYLE} 写实、克制、可信的商业视觉，展现 AI 将分散的零售行业信号"
        "转化为结构化知识和经营决策洞察。人物、门店、商品和数据关系必须真实自然，"
        "禁止芯片、工厂流水线、玩具模型和泛科技装饰。"
    )
    scenes = (
        (
            f"{common} 第一镜：零售信号发现。真实门店、商品、客流和市场变化形成"
            "克制的数据光点；稳定向前运镜，约 5 秒。禁止任何文字、Logo、水印和"
            "伪界面文案；不循环、不倒放。"
        ),
        (
            f"{common} 第二镜：结构化知识形成。不同零售信号自然汇聚为清晰的关系"
            "网络、趋势层次和知识结构；连续横向运镜，约 5 秒。禁止任何文字、Logo、"
            "水印、芯片和工厂意象；不循环、不倒放。"
        ),
        (
            f"{common} 第三镜：经营决策支持。分析结果进入真实商业决策场景，体现"
            "趋势判断、机会识别和行动方向；镜头稳定收束并留下自然片尾空间，约 5 秒。"
            "禁止任何文字、Logo、水印和伪界面文案；不循环、不倒放。"
        ),
    )
    return PromptSet(
        cover=(
            f"{common} 官网 Hero 主视觉，16:9 横构图。右侧是真实零售行业分析与"
            "决策场景，中部用克制的数据节点表现多源信号汇聚，左侧保持自然、干净的"
            "深海军蓝留白，供网页标题使用。禁止任何文字、Logo、水印和发光品牌字；"
            "不循环、不表现连续动作。"
        ),
        body_images=[],
        video=(
            f"{common} 官网展示视频由零售信号发现、结构化知识形成、经营决策支持"
            "三个连续镜头组成。禁止任何文字、Logo、水印和伪界面文案；不循环、不倒放。"
        ),
        version=HOMEPAGE_PROMPT_VERSION,
        video_scenes=scenes,
    )
