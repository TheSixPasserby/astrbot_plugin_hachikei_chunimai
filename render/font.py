"""统一字体加载：优先项目自带字体，其次系统常见中文字体，最后回退默认。"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont


# 常见中文字体候选路径（跨平台）。依次尝试，命中即用。
_CANDIDATE_FONTS = [
    # 项目自带（用户可放入 static/fonts/）
    "static/fonts/NotoSansCJK-Regular.ttc",
    "static/fonts/NotoSansCJKsc-Regular.otf",
    "static/fonts/NotoSansSC-Regular.ttf",
    # Linux（AstrBot Docker 容器常见）
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
]

_BOLD_FONTS = [
    "static/fonts/NotoSansCJK-Bold.ttc",
    "static/fonts/NotoSansCJKsc-Bold.otf",
    "static/fonts/NotoSansSC-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
]

_cache: dict[tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _find_font(candidates: list[str]) -> str | None:
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def get_font(size: int = 20, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """获取中文字体。找不到任何候选时回退到 Pillow 默认字体。

    Args:
        size: 字号。
        bold: 是否优先粗体字库。
    """
    key = (size, bold)
    if key in _cache:
        return _cache[key]

    path = _find_font(_BOLD_FONTS if bold else _CANDIDATE_FONTS)
    if path is None:
        path = _find_font(_CANDIDATE_FONTS)

    if path is not None:
        try:
            font = ImageFont.truetype(path, size)
        except OSError:
            font = ImageFont.load_default()
    else:
        font = ImageFont.load_default()

    _cache[key] = font
    return font
