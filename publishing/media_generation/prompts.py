"""Deterministic ZeroRealm prompts for generated publishing media."""

from __future__ import annotations

from dataclasses import dataclass

from publishing.article import Article


DAILY_PROMPT_VERSION = "daily-v3-reviewed"
HOMEPAGE_PROMPT_VERSION = "homepage-v3"

BRAND_STYLE = (
    "ZeroRealm AI 品牌视觉：商业纪实摄影，深海军蓝、克制的科技蓝和"
    "少量翡翠绿，真实自然光线，真实商品与柜机比例，可信、清晰、现代，"
    "适合智能柜运营负责人；禁止任何文字、Logo、水印和可读界面。"
)


@dataclass(frozen=True)
class PromptSet:
    cover: str
    body_images: list[str]
    video: str
    version: str
    video_scenes: tuple[str, ...] = ()


def build_daily_prompts(article: Article, body_image_count: int = 3) -> PromptSet:
    """Build documentary smart-cabinet operations prompts."""
    context = "；".join(article.summary[:3])
    common = (
        f"{BRAND_STYLE} 主题：{article.title}。核心内容：{context}。"
        "场景必须来自真实智能柜运营现场，画面重点是柜机、商品、货道、"
        "补货动作和经营观察。"
    )
    roles = [
        "商品与货道：近距离记录真实商品陈列、空货道或周转差异。",
        "补货与库存：运营人员核对商品并进行真实补货，动作自然。",
        "小范围调整：运营人员调整少量 SKU 或陈列位置，体现可逆测试。",
    ]
    if body_image_count > len(roles):
        roles.extend(
            f"正文配图 {index}：围绕当天主题补充一个独立、可解释的商业场景。"
            for index in range(len(roles) + 1, body_image_count + 1)
        )

    return PromptSet(
        cover=(
            f"{common} 公众号封面，运营现场，超宽横构图，真实智能柜与商品"
            "作为唯一视觉主体，主体居中偏右，左侧保留安全留白，"
            "不渲染任何文字。"
        ),
        body_images=[f"{common} {role} 16:9 横构图。" for role in roles[:body_image_count]],
        video=(
            f"{common} 生成一条约 15 秒的 9:16 竖屏短视频，"
            "用 3 个连贯镜头表现检查货道、核对库存、小范围调整，镜头稳定，"
            "不渲染字幕或品牌文字，结尾停在调整后的真实柜机。"
        ),
        version=DAILY_PROMPT_VERSION,
    )


def build_homepage_prompts() -> PromptSet:
    """Build one coherent smart-cabinet operator workflow."""
    common = (
        "商业纪实摄影，深海军蓝、克制的科技蓝和少量翡翠绿，写实、克制、"
        "可信。现代写字楼或高校内的真实智能柜运营场景，柜机、商品、货道和"
        "人物比例真实自然。"
    )
    scenes = (
        (
            f"{common} 第一镜：检查智能柜。亚洲智能柜运营负责人打开柜门，"
            "沿货道逐层检查商品陈列，发现一个明显缺货位置和两个周转较慢的"
            "商品排面。稳定的肩后跟拍，约 5 秒。禁止任何文字、Logo、水印、"
            "可读包装和可读屏幕；不循环、不倒放。"
        ),
        (
            "TOP-DOWN cinematic commercial shot, camera directly overhead. A dark navy "
            "operations table fills the entire frame. ONLY hands visible, slowly sorting "
            "unbranded solid-color grocery package samples: plain boxes, cans and bottles "
            "with absolutely blank surfaces. Blank circular category tokens form three "
            "clear groups for sell-through, stock and margin evidence. Five seconds, "
            "slow lateral camera movement. No faces, standing people, phones, monitors, "
            "photos, handwriting, symbols, numbers, letters or labels. 结构化知识，俯拍，"
            "商品样品与运营证据。禁止任何文字、Logo、水印。不循环、不倒放。"
        ),
        (
            f"{common} 第三镜：补货和陈列调整。回到同一台智能柜，运营负责人"
            "补齐缺货商品，撤下一件慢周转商品并调整两个排面，关上柜门后退一步"
            "确认结果。镜头稳定收束，约 5 秒。禁止任何文字、Logo、水印、可读包装"
            "和可读屏幕；不循环、不倒放。"
        ),
    )
    return PromptSet(
        cover=(
            "商业纪实摄影，16:9 横构图，现代写字楼公共区。右侧一位亚洲智能柜"
            "运营负责人在真实柜机前检查商品货道和库存，手持一件无品牌饮料，神态"
            "专注自然。柜机、商品和空间比例真实，左侧保持深海军蓝的虚化环境与"
            "大面积干净留白，供网页标题使用。禁止任何文字、Logo、水印、可读包装"
            "和可读屏幕；不循环、不表现连续动作。"
        ),
        body_images=[],
        video=(
            f"{common} 官网展示视频由检查智能柜、整理运营证据、执行补货和陈列调整"
            "三个连续镜头组成。禁止任何文字、Logo、水印和可读界面；不循环、不倒放。"
        ),
        version=HOMEPAGE_PROMPT_VERSION,
        video_scenes=scenes,
    )
