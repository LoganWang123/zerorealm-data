"""Programmatic brand image templates (Pillow). No diffusion. No Agnes."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int, font_path: str | None = None) -> ImageFont.ImageFont:
    candidates = []
    if font_path:
        candidates.append(Path(font_path))
    candidates.extend(
        [
            Path("assets/fonts/NotoSansSC-Bold.otf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        ]
    )
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_brand_cover(
    *,
    width: int,
    height: int,
    title: str = "",
    subtitle: str = "ZeroRealm AI｜零域",
    bg: tuple[int, int, int] = (24, 32, 40),
    accent: tuple[int, int, int] = (90, 140, 170),
    font_path: str | None = None,
) -> bytes:
    """Editorial cover with programmatic Chinese overlay (not model-drawn text)."""
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    # Restrained left accent bar
    draw.rectangle((0, 0, max(8, width // 64), height), fill=accent)
    # Soft bottom gradient band
    band_top = int(height * 0.62)
    for y in range(band_top, height):
        factor = (y - band_top) / max(1, height - band_top)
        tone = tuple(int(c + (12 - c) * factor * 0.35) for c in bg)
        draw.line([(0, y), (width, y)], fill=tone)

    brand_font = _load_font(max(18, height // 14), font_path)
    title_font = _load_font(max(22, height // 10), font_path)
    margin = max(24, width // 24)
    draw.text((margin + 12, margin), subtitle, fill=(220, 226, 230), font=brand_font)
    if title:
        # Wrap simply by character count for CJK
        max_chars = max(8, width // max(18, title_font.size))
        lines = [title[i : i + max_chars] for i in range(0, len(title), max_chars)][:3]
        y = int(height * 0.38)
        for line in lines:
            draw.text((margin + 12, y), line, fill=(245, 247, 248), font=title_font)
            y += title_font.size + 10

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_editorial_illustration(
    *,
    width: int,
    height: int,
    label: str = "示意图",
) -> bytes:
    """Neutral editorial placeholder — no fake charts or logos."""
    image = Image.new("RGB", (width, height), (236, 238, 240))
    draw = ImageDraw.Draw(image)
    # Soft geometric plane suggesting retail aisle depth — abstract only
    draw.rectangle(
        (int(width * 0.08), int(height * 0.18), int(width * 0.92), int(height * 0.82)),
        outline=(160, 170, 178),
        width=2,
    )
    draw.line(
        [
            (int(width * 0.2), int(height * 0.75)),
            (int(width * 0.8), int(height * 0.75)),
        ],
        fill=(120, 140, 155),
        width=3,
    )
    font = _load_font(max(16, height // 28))
    # Small schematic label via programmatic text only
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - tw) // 2, height - th - max(16, height // 40)),
        label,
        fill=(90, 100, 110),
        font=font,
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
