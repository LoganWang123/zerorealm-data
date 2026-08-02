"""Create the ZeroRealm industry-map launch article as a WeChat draft only."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

from publishing.wechat.client import WechatClient


ARTICLE_TITLE = "中国无人零售产业图谱 V0.1：从设备交易走向经营系统"
ARTICLE_URL = "https://zerorealm.tech/research/industry-map"
BRAND_EMAIL = "hi@zerorealm.tech"
IMAGE_DIR = Path(r"D:\soft\AI\ZeroRealmAI\Gemini-img\知识图谱\1.0")
COVER_PATH = IMAGE_DIR / "公众号封面.png"
BODY_IMAGE_PATHS = [IMAGE_DIR / "插图2.png", IMAGE_DIR / "插图3.png"]


class DraftClient(Protocol):
    def create_draft(self, articles: list[dict]) -> str: ...

    def get_draft(self, media_id: str) -> dict: ...


def _paragraph(text: str, *, color: str = "#334155", bold: bool = False) -> str:
    weight = "font-weight:600;" if bold else ""
    return (
        '<p style="margin:0 0 16px;font-size:16px;line-height:1.9;'
        f'color:{color};{weight}">{text}</p>'
    )


def _section_title(number: str, title: str) -> str:
    return (
        '<div style="margin:34px 0 18px;padding-left:12px;border-left:4px solid #2563eb;">'
        f'<p style="margin:0 0 4px;font-size:12px;letter-spacing:1px;color:#2563eb;">{number}</p>'
        f'<h2 style="margin:0;font-size:21px;line-height:1.5;color:#0f172a;">{title}</h2>'
        "</div>"
    )


def _image(url: str, alt: str) -> str:
    return (
        '<p style="margin:24px 0 8px;">'
        f'<img src="{url}" alt="{alt}" style="display:block;width:100%;height:auto;" />'
        "</p>"
    )


def build_industry_map_article(
    image_urls: list[str], *, thumb_media_id: str
) -> dict:
    """Build the complete WeChat draft payload from two uploaded image URLs."""
    if len(image_urls) != 2:
        raise ValueError("exactly two body image URLs are required")
    if not thumb_media_id:
        raise ValueError("thumb_media_id is required")

    operating_loop_url, evidence_map_url = image_urls
    layers = [
        ("01", "技术与设备基础设施", "让商品识别、交易、连接与设备控制成为可能。"),
        ("02", "无人零售形态", "把基础能力组合成消费者真正能够使用的零售终端。"),
        ("03", "运营与履约系统", "决定设备完成交易之后，业务能否持续运转。"),
        ("04", "消费场景", "提供真实需求、客流结构与即时消费时机。"),
        ("05", "生态支撑服务", "连接供应链、物流、维护、资金、流量与研究能力。"),
    ]
    layer_rows = "".join(
        '<div style="margin:0 0 10px;padding:13px 14px;background:#f8fafc;'
        'border:1px solid #e2e8f0;border-radius:6px;">'
        f'<p style="margin:0 0 3px;font-size:15px;font-weight:600;color:#0f172a;">'
        f'<span style="color:#2563eb;margin-right:8px;">{number}</span>{name}</p>'
        f'<p style="margin:0;font-size:13px;line-height:1.7;color:#64748b;">{role}</p>'
        "</div>"
        for number, name, role in layers
    )

    body = "".join(
        [
            '<div style="max-width:100%;padding:8px 4px;font-family:-apple-system,'
            'BlinkMacSystemFont,Segoe UI,sans-serif;">',
            '<p style="margin:0 0 12px;font-size:13px;letter-spacing:1px;color:#2563eb;">'
            "ZEROREALM RESEARCH · FREE MAP</p>",
            _paragraph(
                "无人零售并非没有发展，而是经历了一轮从“设备想象”回到“经营现实”的校准。",
                color="#0f172a",
                bold=True,
            ),
            _paragraph(
                "一台设备能够识别商品、完成支付，不等于一门生意已经成立。选品、补货、损耗、巡检、场地和毛利，任何一环不能形成闭环，都可能让技术可用停留在商业不可持续。"
            ),
            _paragraph(
                "为此，ZeroRealm AI 发布《中国无人零售产业图谱 V0.1》。这是一份免费、可公开阅读、可下载，也欢迎行业共同纠错的基础版本。"
            ),
            '<div style="margin:24px 0;padding:18px;background:#eff6ff;border-radius:8px;'
            'border:1px solid #bfdbfe;">'
            '<p style="margin:0 0 8px;font-size:15px;font-weight:600;color:#1d4ed8;">'
            "这份图谱试图回答一个问题</p>"
            '<p style="margin:0;font-size:18px;line-height:1.7;font-weight:600;color:#0f172a;">'
            "无人零售要成为可持续经营系统，究竟需要哪些相互连接的能力？</p></div>",
            _section_title("PART 01", "为什么不能只看设备"),
            _paragraph(
                "2017 年前后的无人零售热潮，最容易被看见的是门店、货柜和识别技术。但真正决定项目长期表现的，往往是更具体、更日常的经营环节。"
            ),
            _image(operating_loop_url, "无人零售经营闭环"),
            '<p style="margin:0 0 20px;font-size:13px;line-height:1.7;color:#64748b;text-align:center;">'
            "设备完成一次交易只是起点，补货、损耗、履约和毛利能够持续成立，才是完整业务。</p>",
            _paragraph(
                "因此，判断一个无人零售项目，不应只问识别是否准确、支付是否顺畅，还要继续追问：单点销售能否覆盖补货、物流、场地、折旧与损耗？异常发生后，谁来处理？这一场景是否存在稳定、足量、可重复的即时消费需求？"
            ),
            _section_title("PART 02", "五层结构：把技术放回经营链"),
            _paragraph(
                "V0.1 将无人零售拆成五个相互依赖的层级。它们不是五条孤立赛道，而是一条从基础能力走向持续经营的链条。"
            ),
            layer_rows,
            _paragraph(
                "沿着 01 到 05 层向下检查，可以更快发现问题究竟出在技术、终端形态、履约系统、消费场景，还是外围服务成本。"
            ),
            _section_title("PART 03", "这份图谱适合谁"),
            _paragraph(
                "运营方可以用它检查技术投入是否真正改善单点经营；设备与软件服务商可以识别自身能力最终服务哪个运营环节；品牌与供应链可以理解商品进入不同场景后的库存和履约条件；研究者可以用统一框架组织公开证据和待验证问题。"
            ),
            _section_title("PART 04", "V0.1 的边界：先把结构讲清楚"),
            _image(evidence_map_url, "公开证据驱动的产业图谱"),
            _paragraph(
                "当前版本先解释产业结构，不提供企业排名，也不表示合作、背书或投资建议。后续版本将依据企业官网、公告、政府文件、招投标、专利与权威媒体等公开材料，逐步补充企业节点、真实案例和可核验关系。"
            ),
            '<div style="margin:26px 0;padding:18px;background:#f8fafc;border-top:3px solid #0f172a;">'
            '<p style="margin:0 0 9px;font-size:15px;font-weight:600;color:#0f172a;">'
            "我们的记录原则</p>"
            '<p style="margin:0;font-size:14px;line-height:1.9;color:#475569;">'
            "公开来源 · 事实、推断与待验证问题分层记录 · 无法核验的关系不进入公开版本</p></div>",
            _section_title("FREE DOWNLOAD", "免费下载图谱 PDF"),
            _paragraph(
                "图谱 V0.1 已在 ZeroRealm AI 官网开放，无需填写邮箱即可下载。微信内可点击文末“阅读原文”进入下载页面。",
                color="#0f172a",
                bold=True,
            ),
            f'<p style="margin:0 0 24px;padding:14px;background:#2563eb;color:#ffffff;'
            f'font-size:15px;line-height:1.7;text-align:center;border-radius:6px;">{ARTICLE_URL}</p>',
            _section_title("OPEN CALL", "公开案例征集"),
            _paragraph(
                "如果你发现可公开核验的无人零售案例、行业线索或事实错误，欢迎附上公开来源链接发送给我们。请勿发送商业秘密、内部经营数据或未经授权的个人信息。"
            ),
            '<div style="margin:28px 0 0;padding:20px 0 0;border-top:1px solid #e2e8f0;">'
            '<p style="margin:0 0 8px;font-size:17px;font-weight:600;color:#0f172a;">'
            "关于 ZeroRealm AI</p>"
            '<p style="margin:0 0 12px;font-size:14px;line-height:1.8;color:#475569;">'
            "ZeroRealm AI 持续关注智能零售、无人零售与终端运营，提供每日经营信号、行业洞察与专题研究。</p>"
            '<p style="margin:0 0 6px;font-size:14px;color:#334155;">'
            "公开案例征集｜资料纠错｜行业合作</p>"
            f'<p style="margin:0;font-size:14px;line-height:1.8;color:#334155;">邮箱：{BRAND_EMAIL}'
            f"<br/>官网：https://zerorealm.tech</p></div>",
            "</div>",
        ]
    )

    return {
        "title": ARTICLE_TITLE,
        "author": "ZeroRealm AI",
        "digest": "免费发布：用五层结构重新理解无人零售，从设备交易走向可持续经营系统。",
        "content": body,
        "content_source_url": ARTICLE_URL,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }


def create_verified_draft(client: DraftClient, article: dict) -> str:
    """Create one draft and verify its title through the WeChat read API."""
    media_id = client.create_draft([article])
    stored = client.get_draft(media_id)
    items = stored.get("news_item", [])
    if not items or items[0].get("title") != article["title"]:
        raise RuntimeError("WeChat draft readback title mismatch")
    return media_id


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    app_id = os.getenv("WECHAT_APPID", "")
    app_secret = os.getenv("WECHAT_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("WECHAT_APPID and WECHAT_SECRET are required")

    required_paths = [COVER_PATH, *BODY_IMAGE_PATHS]
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing article images: {missing}")

    client = WechatClient(app_id, app_secret)
    cover_media_id = client.upload_permanent_image(str(COVER_PATH)).get("media_id", "")
    if not cover_media_id:
        raise RuntimeError("WeChat cover upload returned no media_id")
    image_urls = [client.upload_content_image(str(path)) for path in BODY_IMAGE_PATHS]
    article = build_industry_map_article(image_urls, thumb_media_id=cover_media_id)
    media_id = create_verified_draft(client, article)
    print(f"Draft created and verified: title={ARTICLE_TITLE} media_id={media_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
