"""PIL 工具函数：封面路径、base64 转换、饼图。"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


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


def image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """将 PIL 图片转为 base64 字符串（带 data: 前缀）。"""
    buf = BytesIO()
    img.save(buf, fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"base64://{b64}"


def pie_chart(
    data: dict[str, float],
    title: str = "",
    width: int = 400,
    height: int = 300,
) -> Image.Image:
    """用 Pillow 绘制饼图。"""
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
