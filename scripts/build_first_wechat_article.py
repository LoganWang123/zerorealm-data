"""Build first recovery WeChat article assets locally (no Agnes, no auto-approve)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publishing.media_generation.media_job import attach_image, create_job, can_publish
from publishing.media_generation.programmatic import _load_font

SLUG = "smart-cabinet-five-process-metrics"
TITLE = "智能柜运营，真正该盯的，不只是GMV：5个过程指标看清终端经营质量"
OUT = Path("dist/content-package") / SLUG
MEDIA_GEN = Path("output/media/generated") / SLUG
ARTICLE_DIR = Path("output/articles") / SLUG


DIGEST = (
    "GMV是经营结果，但很多问题在数字变化前就埋下了。"
    "从缺货率、补货及时率、设备在线率、SKU动销率到库存准确率，"
    "这组过程指标更能帮助团队定位终端经营质量。"
)

BODY = """某个点位的智能柜，最近成交感觉明显变差。

运营同事第一反应，往往是：点位不行了？价格高了？商品不对？

这些都可能是原因。但再往下拆，现场还常会看到另一组现象：

- 畅销品多次处于缺货状态
- 补货任务连续出现延迟
- 设备短暂离线，支付或识别受影响
- 货道里堆着不少长期不动的 SKU
- 系统库存和开柜盘点对不上

这时如果只盯 GMV，很容易停在“结果变差了”这一层。

**GMV 很重要，但它首先是结果指标。** 终端经营质量，很多时候隐藏在结果发生变化之前的过程里。

---

## 一、为什么只看 GMV 不够

GMV 回答的是：这个点位最终卖了多少。

它不直接回答：

- 当时有没有货可卖
- 货没了以后多久补回来
- 设备是否稳定在线
- 商品结构是否真正动得起来
- 系统库存是否可信

在智能柜场景里，这些问题往往比“最终成交额”更早暴露经营质量。

所以更稳妥的看法是：

**GMV 用来判断经营结果；过程指标用来定位问题、采取行动。**

二者不是对立关系。

---

## 二、缺货率：有没有货可以卖

**定义（来自 ZeroRealm 指标词典）：**  
应售 SKU/货道中处于缺货状态的比例。

公式口径参考：`stockout_slots / expected_slots`

缺货率高，通常意味着：

- 消费者到柜前，想买的东西不在
- 畅销品断货可能直接损失成交机会
- 后续补货、选品、动销分析都会被扭曲

### 常见误区

1. **把临时下架当成真实缺货。**  
   若运营主动下架、清场、调改货道，不应与真实缺货混算。

2. **低缺货率不一定等于经营优秀。**  
   如果大量滞销品一直“有货”，缺货率可能看起来不高，但动销和毛利并不健康。

3. **不同企业对“应售货道”的定义不同。**  
   统计周期、终端集合、是否含测试订单，都会影响口径。不能把企业内部口径直接当成行业统一标准。

**ZeroRealm 判断：**  
缺货率是“有没有成交机会”的基础指标。它重要，但不能单独证明点位好坏。

---

## 三、补货及时率：发现问题以后，多快能恢复

**定义：**  
在约定时效内完成的补货任务占比。

公式口径参考：`ontime_replenish_tasks / total_replenish_tasks`

缺货识别能力和补货执行能力，是两件事。

- 识别到了缺货，却补不过来：问题在运力、路线、仓配或排班
- 补货很快，但总在错品上补：问题可能在动销与库存准确率

### 使用时注意

- 时效定义会因城市、点位类型、楼宇通行规则不同
- “及时”是相对约定 SLA，不是抽象速度感

**ZeroRealm 判断：**  
补货及时率连接“发现问题”和“恢复供给”。它帮助团队区分：是感知慢，还是执行慢。

---

## 四、设备在线率：设备摆在那里，不等于它真的在营业

**定义：**  
在线设备数占应监控设备数的比例。

公式口径参考：`online_devices / managed_devices`

智能柜不是“放着就会自动卖”。网络、支付、识别、柜门、温控、系统状态，任意一环异常，都可能让设备名义上在点位、实际上难成交。

### 常见误区

- 报废或长期停用设备未移出资产池，会压低在线率
- 短时重连抖动，需要和真正离线故障区分（可与离线率对照观察）

**ZeroRealm 判断：**  
在智能柜场景，在线率首先是运维健康度指标。它回答的是：终端有没有处在可营业状态。

---

## 五、SKU 动销率：SKU 多，不等于商品结构好

**定义：**  
有销量的 SKU 数占总在售 SKU 数的比例。

公式口径参考：`skus_with_sales / active_skus`

货道装得满，不代表结构合理。

更常见的现场情况是：

- 少数畅销 SKU 贡献主要成交
- 一组长尾 SKU 长期不动，却占用货道与补货注意力
- 新品导入期动销天然偏低，不宜直接对标成熟 SKU

### 运营含义

动销率低，通常提示：

- 选品与点位人群不匹配
- 陈列/价格/可见性有问题
- 库存虽在，但“有效供给”不足

**ZeroRealm 判断：**  
SKU 动销率帮助团队区分“货多”和“货有效”。它应与缺货率、补货节奏一起看，避免只扩 SKU 不看结构。

---

## 六、库存准确率：系统库存和柜子里的库存，是不是一回事

**定义：**  
盘点结果与系统库存一致的比例。

公式口径参考：`matched_skus / audited_skus`

账实不一致，会连锁影响：

- 缺货判断失真
- 补货任务被错派或漏派
- 消费者看到“系统有货、开柜没有”
- 经营复盘建立在不可信数据上

### 注意

局部盘点不能直接外推全网；不同企业盘点频率与抽样方式也不同。

**ZeroRealm 判断：**  
库存准确率是过程指标的底座。底座不稳，缺货、补货、动销分析都会被放大误差。

---

## 七、这五个指标，应该一起看

更稳妥的做法，是把它们理解成一组**5个过程指标协同观察**：

- **库存准确率**：系统账和柜内实货是否一致，决定后续判断是否可信
- **缺货率**：有没有货可以卖，反映成交机会是否存在
- **补货及时率**：发现问题以后，多快能恢复供给
- **设备在线率**：终端是否处于可营业状态
- **SKU 动销率**：在售商品里，有多少真正在动

这五个指标各自回答不同经营问题，也**共同影响经营结果**（含 GMV）。它们不是一条单向因果链，而是需要同时观察的一组基础过程指标。

实际经营还受点位、价格、场景、客流、商品策略等因素影响。  
所以请把它理解为：**一组值得同时观察的基础过程指标**，而不是“只需要这五个指标”。

不同企业在数据口径、统计周期、终端定义和业务场景上可能存在差异，实际使用时应结合自身业务口径。

---

## 结尾

**ZeroRealm 判断：**

GMV 是经营结果；真正能帮助团队找到问题并采取行动的，往往是结果发生之前的那些过程指标。

从缺货、补货、在线、动销到库存准确，先把过程看清，再解释结果，通常比只盯成交额更接近现场。

---

ZeroRealm 正在持续整理智能柜 / 无人零售经营指标词典。

**ZeroRealm AI（零域）**  
持续研究智能零售、无人零售、即时零售与终端运营。
"""


TITLE_CANDIDATES = [
    ("A", "智能柜运营，真正该盯的，不只是GMV：5个过程指标看清终端经营质量"),
    ("A", "别只盯GMV：智能柜终端经营要一起看的5个过程指标"),
    ("B", "为什么GMV下降了，你却找不到问题？"),
    ("B", "点位生意变差，先别急着怪选址：先看这5个指标"),
    ("C", "GMV只是结果：智能柜运营真正应该看的5个指标"),
    ("C", "结果之前发生了什么：智能柜经营质量的过程指标视角"),
    ("D", "从缺货率到库存准确率：智能柜运营的5个核心过程指标"),
    ("D", "缺货、补货、在线、动销、账实：智能柜运营的一组基础指标"),
    ("A", "智能柜运营现场最该盯的，往往不是成交额本身"),
    ("C", "把GMV放回结果位：用5个过程指标看终端经营质量"),
]


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def render_cover(bg_path: Path | None, out_path: Path) -> Path:
    width, height = 900, 383
    if bg_path and bg_path.is_file():
        base = Image.open(bg_path).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        # darken for text readability
        overlay = Image.new("RGB", (width, height), (20, 28, 36))
        base = Image.blend(base, overlay, 0.45)
    else:
        base = Image.new("RGB", (width, height), (24, 32, 40))
    draw = ImageDraw.Draw(base)
    draw.rectangle((0, 0, 10, height), fill=(90, 140, 170))
    brand = _load_font(22)
    line1_font = _load_font(32)
    line2_font = _load_font(44)
    sub_font = _load_font(26)
    draw.text((28, 28), "ZeroRealm AI｜零域", fill=(220, 226, 230), font=brand)
    # Two-line title; emphasize「不只是GMV」
    draw.text((28, 118), "智能柜运营，真正该盯的，", fill=(245, 247, 248), font=line1_font)
    draw.text((28, 168), "不只是GMV", fill=(235, 210, 150), font=line2_font)
    draw.text((28, height - 78), "5个过程指标看清终端经营质量", fill=(190, 208, 220), font=sub_font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(out_path, format="PNG", optimize=True)
    return out_path


def _draw_centered_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill) -> None:
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - tw // 2, y - th // 2), text, fill=fill, font=font)


def render_infographic(out_path: Path) -> Path:
    """Collaborative structure: five process metrics jointly influence results (no single causal chain)."""
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), (248, 249, 250))
    draw = ImageDraw.Draw(img)
    title_font = _load_font(34)
    metric_font = _load_font(24)
    center_font = _load_font(26)
    note_font = _load_font(18)

    draw.text((48, 28), "5个过程指标协同影响经营结果", fill=(24, 32, 40), font=title_font)
    draw.text((48, 72), "示意协同关系，非单向因果链", fill=(100, 110, 120), font=note_font)

    cx, cy = width // 2, height // 2 + 20
    # Soft ring suggesting collaboration (not a pipeline)
    draw.ellipse((cx - 210, cy - 140, cx + 210, cy + 140), outline=(180, 198, 210), width=2)

    metrics = [
        ("库存准确率", (cx - 420, cy - 40)),
        ("缺货率", (cx - 160, cy - 210)),
        ("补货及时率", (cx + 160, cy - 210)),
        ("设备在线率", (cx + 420, cy - 40)),
        ("SKU动销率", (cx, cy + 210)),
    ]
    center = (cx, cy)
    line_color = (150, 170, 185)
    for label, (mx, my) in metrics:
        # Undirected soft connector (no arrowheads)
        draw.line((mx, my, center[0], center[1]), fill=line_color, width=2)

    # Center result node
    cr = 88
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(34, 52, 64), outline=(90, 140, 170), width=3)
    _draw_centered_text(draw, (cx, cy - 14), "经营结果", center_font, (245, 247, 248))
    _draw_centered_text(draw, (cx, cy + 18), "（含 GMV）", note_font, (190, 208, 220))

    box_w, box_h = 168, 56
    for label, (mx, my) in metrics:
        left, top = mx - box_w // 2, my - box_h // 2
        draw.rounded_rectangle(
            (left, top, left + box_w, top + box_h),
            radius=10,
            outline=(90, 140, 170),
            width=2,
            fill=(255, 255, 255),
        )
        _draw_centered_text(draw, (mx, my), label, metric_font, (24, 32, 40))

    note = (
        "五个过程指标相互关联、共同影响经营结果；"
        "实际经营需结合点位、商品、价格、场景等因素综合判断。"
        "不同企业口径可能不同，不能当作统一行业标准。"
    )
    note_lines = wrap_text(note, note_font, width - 96, draw)
    ny = height - 78
    for line in note_lines:
        draw.text((48, ny), line, fill=(110, 118, 126), font=note_font)
        ny += 22
    draw.text((48, height - 28), "ZeroRealm AI｜零域", fill=(90, 140, 170), font=note_font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    return out_path


def build_package(
    cover: Path,
    infographic: Path,
    cover_job_id: str,
    infographic_job_id: str,
    *,
    body: str,
) -> Path:
    if OUT.exists():
        shutil.rmtree(OUT)
    for name in ("website", "wechat", "zhihu", "sources", "media"):
        (OUT / name).mkdir(parents=True)
    (OUT / "website" / "article.md").write_text(f"# {TITLE}\n\n{body}\n", encoding="utf-8")
    wechat = f"""# {TITLE}

> {DIGEST}

![](../media/cover.png)

{body}

---

![5个过程指标协同影响经营结果](../media/infographic.png)
"""
    (OUT / "wechat" / "draft.md").write_text(wechat, encoding="utf-8")
    (OUT / "wechat" / "digest.txt").write_text(DIGEST + "\n", encoding="utf-8")
    (OUT / "wechat" / "titles.json").write_text(
        json.dumps(
            {
                "recommended": TITLE,
                "top3": [
                    TITLE,
                    "GMV只是结果：智能柜运营真正应该看的5个指标",
                    "从缺货率到库存准确率：智能柜运营的5个核心过程指标",
                ],
                "candidates": [{"style": s, "title": t} for s, t in TITLE_CANDIDATES],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "zhihu" / "package.json").write_text(
        json.dumps(
            {
                "title": TITLE,
                "excerpt": DIGEST,
                "body": body,
                "topics": ["智能零售", "智能柜", "终端运营", "运营指标"],
                "autoPublish": False,
                "cover": "pending_review",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copy2(cover, OUT / "media" / "cover.png")
    shutil.copy2(infographic, OUT / "media" / "infographic.png")
    (OUT / "sources" / "metrics.json").write_text(
        json.dumps(
            {
                "fromApprovedCatalog": [
                    "stockout-rate",
                    "replenish-ontime-rate",
                    "device-online-rate",
                    "sku-sell-through-rate",
                    "inventory-accuracy",
                ],
                "metric_not_in_catalog": [],
                "disclaimer": "不同企业在数据口径、统计周期、终端定义和业务场景上可能存在差异，实际使用时应结合自身业务口径。",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    metadata = {
        "slug": SLUG,
        "title": TITLE,
        "digest": DIGEST,
        "channels": {
            "website": "draft-only-local",
            "wechat": "ready_for_wechat_review",
            "zhihu": "export-only",
        },
        "media": {
            "cover": "media/cover.png",
            "infographic": "media/infographic.png",
            "coverMediaJobId": cover_job_id,
            "infographicMediaJobId": infographic_job_id,
            "coverReviewStatus": "pending_review",
            "infographicReviewStatus": "pending_review",
            "agnes": False,
        },
        "wechat": {
            "status": "ready_for_wechat_review",
            "massSend": False,
            "apiCalled": False,
        },
        "agnesImageGeneration": False,
    }
    (OUT / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return OUT


def _load_body_from_article() -> str:
    """Read approved article body; do not regenerate prose from embedded template."""
    text = (ARTICLE_DIR / "article.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    # Drop H1 + optional digest blockquote
    i = 0
    if lines and lines[0].startswith("# "):
        i = 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].startswith(">"):
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1
    return "\n".join(lines[i:]).rstrip() + "\n"


def main() -> None:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    body = _load_body_from_article()
    # Keep title/digest wrappers in sync; preserve approved body prose.
    (ARTICLE_DIR / "article.md").write_text(f"# {TITLE}\n\n> {DIGEST}\n\n{body}", encoding="utf-8")
    (ARTICLE_DIR / "digest.txt").write_text(DIGEST + "\n", encoding="utf-8")
    (ARTICLE_DIR / "titles.json").write_text(
        json.dumps(
            {
                "recommended": TITLE,
                "candidates": [{"style": s, "title": t} for s, t in TITLE_CANDIDATES],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    bg_candidates = [
        Path(r"C:\Users\wang'long\.cursor\projects\d-soft-AI-ZeroRealmAI\assets\wechat-first-article-bg.png"),
        Path("output/media/ide-inbox/wechat-first-article-bg.png"),
        Path("output/media/ide-inbox/smart-cabinet-scene-1280x720.png"),
    ]
    bg = next((p for p in bg_candidates if p.is_file()), None)
    cover = render_cover(bg, MEDIA_GEN / "cover.png")
    info = render_infographic(MEDIA_GEN / "infographic.png")

    cover_job = create_job(
        content_id=SLUG,
        content_type="wechat_article",
        channel="wechat",
        purpose="cover",
        title=TITLE,
        width=900,
        height=383,
        aspect_ratio="900:383",
    )
    cover_attached = attach_image(
        cover_job.id,
        cover,
        generator_type="programmatic" if bg is None else "ide_native",
        generator_agent="cursor" if bg else "manual",
    )

    info_job = create_job(
        content_id=SLUG,
        content_type="wechat_article",
        channel="wechat",
        purpose="infographic",
        title=TITLE,
        width=1280,
        height=720,
        aspect_ratio="16:9",
    )
    info_attached = attach_image(
        info_job.id,
        info,
        generator_type="programmatic",
        generator_agent="manual",
    )

    package = build_package(
        cover,
        info,
        cover_attached.id,
        info_attached.id,
        body=body,
    )
    print(
        json.dumps(
            {
                "title": TITLE,
                "digest": DIGEST,
                "article": str(ARTICLE_DIR / "article.md"),
                "cover": str(cover),
                "infographic": str(info),
                "coverMediaJobId": cover_attached.id,
                "coverStatus": cover_attached.status,
                "coverCanPublish": can_publish(cover_attached),
                "infographicMediaJobId": info_attached.id,
                "infographicStatus": info_attached.status,
                "infographicCanPublish": can_publish(info_attached),
                "package": str(package),
                "wechatStatus": "ready_for_wechat_review",
                "agnes": False,
                "massSend": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
