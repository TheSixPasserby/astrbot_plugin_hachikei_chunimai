"""maimai B50 图片渲染。

消费 :class:`~unified.UnifiedScore`，只做排版与绘制，不关心查分器字段。
封面由调用方预取后传入（见 :mod:`cover`）。
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from .emoji import sanitize_emoji
from .font import get_font
from ..unified import UnifiedScore
from ..utils import fmt_fc, fmt_rate

# 配色
_BG = (245, 247, 250, 255)
_HEADER_BG = (66, 133, 244, 255)
_TITLE = (33, 33, 33, 255)
_TEXT = (55, 55, 55, 255)
_MUTED = (130, 130, 130, 255)
_SECTION_BG = (255, 255, 255, 255)
_ROW_ALT = (238, 241, 246, 255)
_DIVIDER = (224, 226, 230, 255)
_ACCENT = (30, 100, 200, 255)


def _fmt_achievements(a: float | None) -> str:
    if a is None:
        return "-"
    return f"{a:.4f}%"


def _fmt_ds(ds: float | None) -> str:
    if ds is None:
        return "?"
    return f"{ds:.1f}"


def _fmt_rating(r: float) -> str:
    return f"{r:.0f}" if r == int(r) else f"{r:.1f}"


def render_b50(
    player_name: str,
    rating: float,
    sections: list[tuple[str, list[UnifiedScore]]],
    covers: dict[int, Image.Image],
    *,
    width: int = 760,
    card_h: int = 56,
) -> Image.Image:
    """渲染 B50 图片。

    Args:
        player_name: 玩家昵称。
        rating: 总 Rating。
        sections: [(分区标题, [UnifiedScore, ...]), ...]，通常为 SD Best 35 + DX Best 15。
        covers: ``music_id -> PIL.Image`` 封面图（缺失项由渲染器用占位图兜底）。
        width: 图片宽度。
        card_h: 单行卡片高度。

    Returns:
        Pillow Image（RGBA）。
    """
    pad = 20
    header_h = 84
    section_title_h = 34
    gap = 14

    total_cards = sum(len(scores) for _, scores in sections)
    height = (
        header_h
        + len(sections) * section_title_h
        + total_cards * card_h
        + (len(sections) - 1) * gap
        + pad * 2
    )

    img = Image.new("RGBA", (width, max(height, 200)), _BG)
    draw = ImageDraw.Draw(img)

    # 页眉
    draw.rectangle([0, 0, width, header_h], fill=_HEADER_BG)
    title_font = get_font(26, bold=True)
    sub_font = get_font(17)
    draw.text((pad, 14), sanitize_emoji(f"🎵 {player_name} 的 Best 50"), font=title_font, fill=(255, 255, 255, 255))
    draw.text((pad, 54), f"Rating: {rating}", font=sub_font, fill=(230, 235, 255, 255))

    y = header_h + pad

    name_font = get_font(15, bold=True)
    small_font = get_font(12)
    meta_font = get_font(13)

    for sec_idx, (sec_title, scores) in enumerate(sections):
        # 分区标题
        draw.text((pad, y + 6), sanitize_emoji(sec_title), font=get_font(18, bold=True), fill=_TITLE)
        y += section_title_h

        for i, s in enumerate(scores):
            top = y
            if i % 2 == 1:
                draw.rectangle([0, top, width, top + card_h], fill=_ROW_ALT)

            # 排名
            rank_text = f"{i + 1:02d}"
            rank_w = 46
            draw.text((pad, top + 18), rank_text, font=name_font, fill=_MUTED)

            # 封面
            cover = covers.get(s.music_id)
            cover_x = pad + rank_w
            if cover is not None:
                thumb = cover.resize((40, 40))
                img.paste(thumb, (cover_x, top + (card_h - 40) // 2))
            else:
                draw.rectangle([cover_x, top + 8, cover_x + 40, top + 48], fill=(200, 200, 200))
            cover_w = 48

            # 曲名 + 难度
            name_x = cover_x + cover_w
            title = sanitize_emoji(s.title)
            diff = s.level_label or "?"
            type_tag = f"[{s.type.upper()}] " if s.type else ""
            draw.text((name_x, top + 6), f"{type_tag}{title}", font=name_font, fill=_TITLE)
            draw.text((name_x, top + 30), f"{diff}  |  定数 {_fmt_ds(s.ds)}", font=small_font, fill=_MUTED)

            # 右侧：达成率 / 评级 / Rating
            rate_x = width - pad - 210
            draw.text((rate_x, top + 8), _fmt_achievements(s.achievements), font=meta_font, fill=_ACCENT)
            draw.text((rate_x, top + 30), fmt_rate(s.rate) if s.rate else "-", font=small_font, fill=_TEXT)

            fc_x = width - pad - 130
            draw.text((fc_x, top + 8), fmt_fc(s.fc) if s.fc else "-", font=small_font, fill=_MUTED)
            draw.text((fc_x, top + 30), "FC", font=small_font, fill=_MUTED)

            ra_x = width - pad - 60
            draw.text((ra_x, top + 8), _fmt_rating(s.rating), font=get_font(16, bold=True), fill=_TITLE)
            draw.text((ra_x, top + 30), "Rating", font=small_font, fill=_MUTED)

            y += card_h

        if sec_idx < len(sections) - 1:
            y += gap

    return img
