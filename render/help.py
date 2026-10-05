"""帮助图渲染：用 Pillow 绘制帮助菜单图片（不依赖 Chromium）。"""

from __future__ import annotations

from PIL import Image, ImageDraw

from .emoji import sanitize_emoji
from .font import get_font


# 配色
_BG = (255, 255, 255, 255)
_HEADER_BG = (66, 133, 244, 255)
_TITLE = (33, 33, 33, 255)
_TEXT = (60, 60, 60, 255)
_MUTED = (120, 120, 120, 255)
_CMD = (30, 100, 200, 255)
_STAR = (230, 150, 0, 255)
_DIVIDER = (220, 220, 220, 255)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def render_help(
    sections: dict,
    current_game: str = "maimai",
    group_game: str | None = None,
    width: int = 640,
) -> Image.Image:
    """把结构化帮助数据渲染成 PNG 图片。

    Args:
        sections: 与 ``command.help.HELP_SECTIONS`` 同构的结构化数据。
        current_game / group_game: 用于动态页眉。
        width: 图片宽度（高度自适应）。

    Returns:
        Pillow Image 对象。
    """
    game_label = "maimai DX" if current_game == "maimai" else "CHUNITHM"
    group_label = ""
    if group_game is not None:
        group_label = "maimai DX" if group_game == "maimai" else "CHUNITHM"

    # 先测量高度
    pad = 20
    header_h = 90
    row_h = 30
    section_gap = 26

    def _section_lines(sec: dict) -> int:
        return len(sec["commands"])

    total_rows = sum(_section_lines(s) for s in sections.values())
    total_sections = len(sections)
    # 页眉 + 提示 + 各分区（标题行 + 表头行 + 数据行）+ 分区间隔
    hint_h = 60
    height = (
        header_h
        + hint_h
        + total_sections * (section_gap + 34)  # 标题 + 表头
        + total_rows * row_h
        + pad * 2
    )

    img = Image.new("RGBA", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    # 页眉
    draw.rectangle([0, 0, width, header_h], fill=_HEADER_BG)
    title_font = get_font(26, bold=True)
    sub_font = get_font(16)
    draw.text((pad, 14), sanitize_emoji("🎵 maimai DX & CHUNITHM 综合助手"), font=title_font, fill=(255, 255, 255, 255))
    sub = f"当前查询游戏: {game_label}"
    if group_label:
        sub += f"  |  群默认: {group_label}"
    draw.text((pad, 52), sub, font=sub_font, fill=(230, 235, 255, 255))

    y = header_h + 14
    hint_font = get_font(13)
    hints = [
        "· 首次使用请发送「绑定账号」查看绑定指引",
        "· 带 ⭐ 的命令支持游戏路由：前缀 mai/chu 可强制指定游戏",
        "· 发送「同步数据 水鱼/落雪」后发送街机二维码即可同步成绩",
    ]
    for h in hints:
        draw.text((pad, y), sanitize_emoji(h), font=hint_font, fill=_MUTED)
        y += 18

    y += 4
    sec_title_font = get_font(17, bold=True)
    col_cmd = pad
    col_alias = pad + 250
    col_desc = pad + 360

    for key, sec in sections.items():
        # 分区标题
        draw.text((pad, y), sanitize_emoji(f"{sec['emoji']} {sec['title']}"), font=sec_title_font, fill=_TITLE)
        y += 26
        # 表头
        header_font = get_font(12, bold=True)
        draw.text((col_cmd, y), "命令", font=header_font, fill=_MUTED)
        draw.text((col_alias, y), "别名", font=header_font, fill=_MUTED)
        draw.text((col_desc, y), "说明", font=header_font, fill=_MUTED)
        y += 18
        # 数据行
        row_font = get_font(14)
        for c in sec["commands"]:
            cmd_text = sanitize_emoji(c["cmd"])
            if c.get("star"):
                cmd_text += " ★"
            draw.text((col_cmd, y), cmd_text, font=row_font, fill=_CMD)
            draw.text((col_alias, y), sanitize_emoji(c["alias"]), font=row_font, fill=_TEXT)
            draw.text((col_desc, y), sanitize_emoji(c["desc"]), font=row_font, fill=_TEXT)
            y += row_h
        # 分区间隔
        draw.line([pad, y - 6, width - pad, y - 6], fill=_DIVIDER, width=1)
        y += section_gap

    return img
