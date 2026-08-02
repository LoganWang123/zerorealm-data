"""Build and update the evidence-backed ZeroRealm industry-map WeChat draft."""

from __future__ import annotations

import os
import re
from html import escape
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

from publishing.wechat.client import WechatClient


ARTICLE_TITLE = "中国无人零售产业链图谱 V0.2：首批企业、产品与真实案例"
ARTICLE_URL = "https://zerorealm.tech/research/industry-map"
BRAND_EMAIL = "hi@zerorealm.tech"
DEFAULT_DRAFT_MEDIA_ID = "csbrZswCx_5hmuZ_bqWc69eVU-wSK2QwwA2vhXiPdFIMzW4Np_2-9AAsr3cA098O"
IMAGE_DIR = Path(r"D:\soft\AI\ZeroRealmAI\Gemini-img\知识图谱\1.0")
COVER_PATH = IMAGE_DIR / "公众号封面.png"
BODY_IMAGE_PATHS = [IMAGE_DIR / "插图2.png", IMAGE_DIR / "插图3.png"]


class DraftClient(Protocol):
    def create_draft(self, articles: list[dict]) -> str: ...

    def update_draft(self, media_id: str, index: int, article: dict) -> dict: ...

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
        f'<img src="{escape(url, quote=True)}" alt="{alt}" style="display:block;width:100%;height:auto;" />'
        "</p>"
    )


def _node(name: str, role: str, products: str, scenarios: str, source: str) -> str:
    return (
        '<div style="margin:0 0 12px;padding:15px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:7px;">'
        f'<p style="margin:0 0 4px;font-size:17px;font-weight:600;color:#0f172a;">{name}</p>'
        f'<p style="margin:0 0 6px;font-size:13px;color:#2563eb;">{role}</p>'
        f'<p style="margin:0 0 4px;font-size:14px;line-height:1.7;color:#475569;"><b>产品：</b>{products}</p>'
        f'<p style="margin:0 0 4px;font-size:14px;line-height:1.7;color:#475569;"><b>场景：</b>{scenarios}</p>'
        f'<p style="margin:0;font-size:12px;line-height:1.7;color:#64748b;">A 级公开来源：{source} · 核验日期 2026-08-02</p>'
        "</div>"
    )


def _case(name: str, scenario: str, solution: str, fact: str) -> str:
    return (
        '<div style="margin:0 0 12px;padding:15px;border-left:3px solid #2563eb;background:#ffffff;">'
        f'<p style="margin:0 0 4px;font-size:16px;font-weight:600;color:#0f172a;">{name}</p>'
        f'<p style="margin:0 0 6px;font-size:12px;color:#2563eb;">{scenario} · {solution}</p>'
        f'<p style="margin:0;font-size:14px;line-height:1.8;color:#475569;">{fact}</p>'
        "</div>"
    )


def build_industry_map_article(image_urls: list[str], *, thumb_media_id: str) -> dict:
    """Build the corrected V0.2 WeChat draft payload."""
    if len(image_urls) != 2:
        raise ValueError("exactly two body image URLs are required")
    if not thumb_media_id:
        raise ValueError("thumb_media_id is required")

    operating_loop_url, evidence_map_url = image_urls
    stages = [
        ("01", "设备与技术", "机器视觉、IoT、制冷、支付与运营软件"),
        ("02", "终端形态", "售货机、智能柜、无人便利店与智能领用仓"),
        ("03", "运营履约", "选址、商品、补货、库存、维护与客服"),
        ("04", "场景入口", "办公、学校、工厂、交通、医疗与文旅"),
    ]
    stage_rows = "".join(
        '<div style="margin:0 0 9px;padding:12px 14px;background:#eff6ff;border-radius:6px;">'
        f'<p style="margin:0 0 3px;font-size:15px;font-weight:600;color:#0f172a;">'
        f'<span style="color:#2563eb;margin-right:8px;">{number}</span>{title}</p>'
        f'<p style="margin:0;font-size:13px;line-height:1.7;color:#64748b;">{detail}</p></div>'
        for number, title, detail in stages
    )
    nodes = "".join(
        [
            _node("友宝在线", "智能零售终端运营与平台服务", "智能售货机、智能货柜、智能咖啡机、代运营", "学校、工厂、写字楼、交通枢纽", "友宝在线官网"),
            _node("丰e足食", "办公室小场景无人零售运营", "AI 智能柜、自动贩卖机、直营运营服务", "办公室、工厂物流、休闲娱乐场所", "丰e足食官网"),
            _node("云拿科技", "AI 无人店与智能领用仓解决方案", "3D 机器视觉、多传感融合、AI 无人店、智能领用仓", "交通、学校、科研机构、药店、工业领用", "云拿科技案例库"),
            _node("合豚科技", "无人零售软硬件与 SaaS 服务", "AI 视觉柜、智能售货机、零售 SaaS、IoT 管理", "品牌动销、企业私域、售货机运营", "合豚科技官网"),
            _node("嗨便利", "动态视觉智能售货柜", "AI 动态视觉柜、智能售货柜", "写字楼、酒店、学校、医院、交通、工厂", "嗨便利官网"),
            _node("映翰通", "边缘视觉智能售货柜方案", "边缘视觉识别、AI 智能售货柜、运营平台", "无人售货、智能柜运营", "映翰通产品页"),
        ]
    )
    cases = "".join(
        [
            _case("苏州交投能源 AI 无人店", "交通能源", "AI 无人店", "云拿官网披露该项目于 2020 年引入无人店，并公开了员工使用与开店后的经营描述。"),
            _case("上海商学院无人零售项目", "学校", "AI 无人店", "云拿案例库将项目描述为丰富师生就餐选择的“第二个食堂”，并兼具实践基地用途。"),
            _case("李政道研究所无人零售项目", "科研机构", "AI 无人零售", "云拿案例库公开列出李政道研究所引入其 AI 无人零售解决方案。"),
            _case("雷允上 AI 无人药店", "医药零售", "24 小时 AI 无人药店", "云拿案例库公开列出该项目覆盖非处方药与健康日用品。"),
        ]
    )

    body = "".join(
        [
            '<div style="max-width:100%;padding:8px 4px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">',
            '<p style="margin:0 0 12px;font-size:13px;letter-spacing:1px;color:#2563eb;">ZEROREALM RESEARCH · EVIDENCE MAP</p>',
            _paragraph("这是一份主动修订，也是一份更接近“产业链图谱”应有形态的版本。", color="#0f172a", bold=True),
            _paragraph("原 V0.1 更准确地说，是一套经营系统分析框架：它解释了无人零售涉及哪些能力，却没有展示企业、产品和实际案例。继续把它称作产业链图谱并不严谨。"),
            _paragraph("因此，我们将原内容更名为《中国无人零售经营系统框架 V0.1》，并发布《中国无人零售产业链图谱 V0.2（首批核验版）》。"),
            '<div style="margin:24px 0;padding:18px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;">'
            '<p style="margin:0;font-size:16px;line-height:1.8;font-weight:600;color:#0f172a;">V0.2 新增：产业链结构、6 个企业产品节点、4 个实际案例，以及逐项公开来源和核验日期。</p></div>',
            _section_title("PART 01", "无人零售产业链如何连接"),
            _paragraph("无人零售不是一台设备，而是从能力供给到消费场景的一条经营链。箭头只表示业务承接顺序，不自动代表企业之间存在合作关系。"),
            stage_rows,
            _image(operating_loop_url, "无人零售经营闭环"),
            _section_title("PART 02", "首批企业与产品节点"),
            _paragraph("本版只收录能够从企业官网、上市文件或监管披露直接核验的公开信息。企业自述只证明其公开披露，不代表 ZeroRealm AI 对产品效果作独立验证。"),
            nodes,
            _section_title("PART 03", "公开可核验的实际场景案例"),
            cases,
            _paragraph("以上案例均来自方案提供方公开案例库。V0.2 不把单方公开材料进一步推断为市场排名、长期经营效果或商业背书。"),
            _section_title("PART 04", "我们如何控制图谱边界"),
            _image(evidence_map_url, "公开证据驱动的产业图谱"),
            '<div style="margin:22px 0;padding:18px;background:#f8fafc;border-top:3px solid #0f172a;">'
            '<p style="margin:0 0 9px;font-size:15px;font-weight:600;color:#0f172a;">样本不等于全量名录</p>'
            '<p style="margin:0;font-size:14px;line-height:1.9;color:#475569;">收录不表示合作、背书、排名或投资建议；无法核验的企业能力和关系不进入公开版本。</p></div>',
            _section_title("ONLINE", "查看完整图谱与来源链接"),
            _paragraph("完整企业节点、案例来源和经营系统框架 PDF 已在官网公开。由于微信内可能限制未备案域名，请长按复制下方网址后，用手机系统浏览器打开。", color="#0f172a", bold=True),
            f'<p style="margin:0 0 24px;padding:14px;background:#2563eb;color:#ffffff;font-size:15px;line-height:1.7;text-align:center;border-radius:6px;">{ARTICLE_URL}</p>',
            _section_title("OPEN CALL", "公开案例征集"),
            _paragraph("如果你发现可公开核验的无人零售案例、企业产品或事实错误，欢迎附公开来源链接发送给我们。请勿发送商业秘密、内部经营数据或未经授权的个人信息。"),
            '<div style="margin:28px 0 0;padding:20px 0 0;border-top:1px solid #e2e8f0;">'
            '<p style="margin:0 0 8px;font-size:17px;font-weight:600;color:#0f172a;">关于 ZeroRealm AI</p>'
            '<p style="margin:0 0 12px;font-size:14px;line-height:1.8;color:#475569;">ZeroRealm AI 持续关注智能零售、无人零售与终端运营，提供每日经营信号、行业洞察与专题研究。</p>'
            '<p style="margin:0 0 6px;font-size:14px;color:#334155;">公开案例征集｜资料纠错｜行业合作</p>'
            f'<p style="margin:0;font-size:14px;line-height:1.8;color:#334155;">邮箱：{BRAND_EMAIL}<br/>官网：https://zerorealm.tech</p></div>',
            "</div>",
        ]
    )

    return {
        "title": ARTICLE_TITLE,
        "author": "ZeroRealm AI",
        "digest": "主动修订 V0.1：首批补入企业、产品、真实场景案例及逐项公开来源。",
        "content": body,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }


def create_verified_draft(client: DraftClient, article: dict) -> str:
    media_id = client.create_draft([article])
    return _verify_draft(client, media_id, article)


def update_verified_draft(client: DraftClient, media_id: str, article: dict) -> str:
    client.update_draft(media_id, 0, article)
    return _verify_draft(client, media_id, article)


def _verify_draft(client: DraftClient, media_id: str, article: dict) -> str:
    stored = client.get_draft(media_id)
    items = stored.get("news_item", [])
    if not items or items[0].get("title") != article["title"]:
        raise RuntimeError("WeChat draft readback title mismatch")
    stored_content = items[0].get("content", "")
    required = ["友宝在线", "丰e足食", "云拿科技", "苏州交投能源", BRAND_EMAIL]
    if any(text not in stored_content for text in required):
        raise RuntimeError("WeChat draft readback content mismatch")
    if items[0].get("content_source_url") or "阅读原文" in stored_content:
        raise RuntimeError("WeChat draft unexpectedly contains a source link")
    return media_id


def _existing_assets(stored_article: dict) -> tuple[str, list[str]]:
    thumb_media_id = stored_article.get("thumb_media_id", "")
    image_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)', stored_article.get("content", ""))
    return thumb_media_id, image_urls[:2]


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    app_id = os.getenv("WECHAT_APPID", "")
    app_secret = os.getenv("WECHAT_SECRET", "")
    media_id = os.getenv("WECHAT_INDUSTRY_MAP_DRAFT_ID", DEFAULT_DRAFT_MEDIA_ID)
    if not app_id or not app_secret:
        raise RuntimeError("WECHAT_APPID and WECHAT_SECRET are required")

    client = WechatClient(app_id, app_secret)
    stored = client.get_draft(media_id)
    items = stored.get("news_item", [])
    if not items:
        raise RuntimeError("Existing WeChat draft has no article")
    thumb_media_id, image_urls = _existing_assets(items[0])

    if not thumb_media_id:
        thumb_media_id = client.upload_permanent_image(str(COVER_PATH)).get("media_id", "")
    if len(image_urls) != 2:
        image_urls = [client.upload_content_image(str(path)) for path in BODY_IMAGE_PATHS]

    article = build_industry_map_article(image_urls, thumb_media_id=thumb_media_id)
    update_verified_draft(client, media_id, article)
    print(f"Draft updated and verified: title={ARTICLE_TITLE} media_id={media_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
