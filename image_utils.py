"""PIL 工具函数：文字渲染、渐变、圆角、base64 转换。"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


# --- 字体路径（需要用户放置在 static/fonts/ 下） ---

def _font_path(name: str, data_dir: Path) -> Path:
    return data_dir / "static" / "fonts" / name


class DrawText:
    """封装 PIL 文字绘制，支持自动加载字体。"""

    def __init__(self, draw: ImageDraw.ImageDraw, font_path: str) -> None:
        self._draw = draw
        self._font_path = font_path

    def get_box(self, text: str, size: int) -> tuple[float, float, float, float]:
        return ImageFont.truetype(self._font_path, size).getbbox(text)

    def draw(
        self,
        x: int,
        y: int,
        size: int,
        text: Union[str, int, float],
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        anchor: str = "lt",
        stroke_width: int = 0,
        stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 0),
        multiline: bool = False,
    ) -> None:
        font = ImageFont.truetype(self._font_path, size)
        if multiline:
            self._draw.multiline_text(
                (x, y), str(text), color, font, anchor,
                stroke_width=stroke_width, stroke_fill=stroke_fill,
            )
        else:
            self._draw.text(
                (x, y), str(text), color, font, anchor,
                stroke_width=stroke_width, stroke_fill=stroke_fill,
            )


def tricolor_gradient(
    width: int,
    height: int,
    color1: tuple[int, int, int] = (124, 129, 255),
    color2: tuple[int, int, int] = (193, 247, 225),
    color3: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """绘制三色渐变背景。"""
    array = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        if y < height * 0.4:
            ratio = y / (height * 0.4)
            color = (1 - ratio) * np.array(color1) + ratio * np.array(color2)
        else:
            ratio = (y - height * 0.4) / (height * 0.6)
            color = (1 - ratio) * np.array(color2) + ratio * np.array(color3)
        array[y, :] = np.clip(color, 0, 255)
    return Image.fromarray(array).convert("RGBA")


def rounded_corners(
    image: Image.Image,
    radius: int,
    corners: tuple[bool, bool, bool, bool] = (True, True, True, True),
) -> Image.Image:
    """给图片添加圆角。"""
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, image.size[0], image.size[1]), radius, fill=255, corners=corners
    )
    new_im = ImageOps.fit(image, mask.size)
    new_im.putalpha(mask)
    return new_im


def music_picture_path(music_id: int | str, cover_dir: Path) -> Path:
    """获取歌曲封面图路径，带 fallback。"""
    mid = int(music_id)
    p = cover_dir / f"{mid}.png"
    if p.exists():
        return p
    if mid > 100000:
        p2 = cover_dir / f"{mid - 100000}.png"
        if p2.exists():
            return p2
    if 1000 < mid < 10000 or 10000 < mid <= 11000:
        for alt in [mid + 10000, mid - 10000]:
            p3 = cover_dir / f"{alt}.png"
            if p3.exists():
                return p3
    return cover_dir / "11000.png"


def text_to_image(
    text: str,
    font_path: str | None = None,
    font_size: int = 24,
    fg: tuple[int, int, int] = (0, 0, 0),
    bg: tuple[int, int, int] = (255, 255, 255),
    padding: int = 10,
    margin: int = 4,
) -> Image.Image:
    """将多行文本渲染为图片。"""
    if font_path is None:
        font = ImageFont.load_default()
    else:
        font = ImageFont.truetype(font_path, font_size)
    lines = text.strip().split("\n")
    max_width = 0
    line_height = 0
    for line in lines:
        l, t, r, b = font.getbbox(line)
        max_width = max(max_width, r)
        line_height = max(line_height, b)
    w = max_width + padding * 2
    h = line_height * len(lines) + margin * (len(lines) - 1) + padding * 2
    im = Image.new("RGB", (w, h), color=bg)
    draw = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        draw.text((padding, padding + i * (margin + line_height)), line, font=font, fill=fg)
    return im


def image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """将 PIL 图片转为 base64 字符串（带 data: 前缀）。"""
    buf = BytesIO()
    img.save(buf, fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"base64://{b64}"


def base64_to_image(b64: str) -> Image.Image:
    """将 base64 字符串还原为 PIL 图片。"""
    if b64.startswith("base64://"):
        b64 = b64[9:]
    return Image.open(BytesIO(base64.b64decode(b64)))


def pie_chart(
    data: dict[str, float],
    title: str = "",
    width: int = 400,
    height: int = 300,
) -> Image.Image:
    """用 Pillow 绘制饼图（替代 pyecharts + Playwright）。"""
    import math

    total = sum(data.values())
    if total == 0:
        return Image.new("RGB", (width, height), (255, 255, 255))

    colors = [
        (66, 133, 244), (234, 67, 53), (251, 188, 4), (52, 168, 83),
        (156, 39, 176), (255, 87, 34), (0, 188, 212), (139, 195, 74),
        (255, 152, 0), (121, 85, 72), (158, 158, 158), (96, 125, 139),
    ]

    im = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(im)

    cx, cy = width // 3, height // 2
    radius = min(cx, cy) - 20
    start_angle = 0.0

    for i, (label, value) in enumerate(data.items()):
        sweep = 360 * value / total
        color = colors[i % len(colors)]
        draw.pieslice(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            start=start_angle, end=start_angle + sweep, fill=color, outline=(255, 255, 255),
        )
        start_angle += sweep

    # 图例
    legend_x = width * 2 // 3
    legend_y = 20
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    for i, (label, value) in enumerate(data.items()):
        color = colors[i % len(colors)]
        draw.rectangle([legend_x, legend_y + i * 22, legend_x + 14, legend_y + i * 22 + 14], fill=color)
        pct = f"{value / total * 100:.1f}%"
        draw.text((legend_x + 20, legend_y + i * 22), f"{label} ({pct})", fill=(0, 0, 0), font=font)

    if title:
        try:
            title_font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            title_font = ImageFont.load_default()
        draw.text((10, 5), title, fill=(0, 0, 0), font=title_font)

    return im
