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
        "深海军蓝、克制的科技蓝和少量翡翠绿，写实、克制、可信的商业视觉，"
        "适合商业决策者。展现 AI 将分散的零售行业信号"
        "转化为结构化知识和经营决策洞察。人物、门店、商品和数据关系真实自然。"
    )
    scenes = (
        (
            f"{common} 第一镜：零售信号发现。现代精品超市内，亚洲零售研究团队沿"
            "商品货架进行现场观察，对比陈列、库存与顾客选择，并用手势交流发现；"
            "少量蓝绿色半透明光点随视线从商品自然汇聚。稳定向前运镜，约 5 秒。"
            "禁止任何文字、Logo、水印和可读招牌；不循环、不倒放。"
        ),
        (
            "TOP-DOWN cinematic commercial shot, camera directly overhead. A dark navy "
            "research table fills the entire frame. ONLY hands visible, slowly sorting "
            "unbranded solid-color grocery package samples: plain boxes, cans and bottles "
            "with absolutely blank surfaces. Blank circular category tokens form three "
            "clear groups while subtle cyan lines connect related items. Five seconds, "
            "slow lateral camera movement. No faces, standing people, phones, monitors, "
            "photos, handwriting, symbols, numbers, letters or labels. 结构化知识，俯拍，"
            "食品饮料包装样品。禁止任何文字、Logo、水印。不循环、不倒放。"
        ),
        (
            f"{common} 第三镜：经营决策支持。亚洲管理团队举行零售经营会议，桌面"
            "摆放商品样品与平板，墙面仅呈现无字的彩色趋势曲线；负责人确认重点机会，"
            "团队形成行动共识。镜头稳定收束并留下自然片尾空间，约 5 秒。禁止任何文字、"
            "Logo、水印和可读屏幕；不循环、不倒放。"
        ),
    )
    return PromptSet(
        cover=(
            "商业纪实摄影，16:9 横构图，现代精品超市内景。右侧的零售策略团队在"
            "真实商品货架旁共同查看一台没有可见界面的平板；克制的蓝绿半透明光流"
            "从不同商品区域自然汇聚到平板，表达市场信号汇总和趋势判断。人物神态"
            "专业自然，商品和空间比例真实。左侧保持深海军蓝的模糊过道与大面积干净"
            "留白，供网页标题使用。禁止任何文字、Logo、水印、可读招牌和界面文案；"
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
