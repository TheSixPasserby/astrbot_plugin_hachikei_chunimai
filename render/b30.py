"""CHUNITHM B30 图片渲染。

消费 :class:`~unified.UnifiedScore`，只做排版与绘制，不关心查分器字段。
布局区别于 maimai B50：每行展示分数 / 评级 / CLEAR / FC / Rating。
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from .emoji import sanitize_emoji
from .font import get_font
from ..unified import UnifiedScore
from ..chu_data import CHU_FC_LABELS, CHU_CHAIN_LABELS, CHU_CLEAR_LABELS

# 配色（与 B50 保持一致，标题色改青绿以示区分）
_BG = (245, 247, 250, 255)
_HEADER_BG = (38, 166, 154, 255)
_TITLE = (33, 33, 33, 255)
_TEXT = (55, 55, 55, 255)
_MUTED = (130, 130, 130, 255)
_ROW_ALT = (238, 241, 246, 255)
_DIVIDER = (224, 226, 230, 255)
_ACCENT = (0, 137, 123, 255)


def _fmt_score(score: int | None) -> str:
    if score is None:
        return "-"
    return f"{score:,}"


def _fmt_rating(r: float) -> str:
    return f"{r:.2f}"


def _fmt_ds(ds: float | None) -> str:
    if ds is None:
        return "?"
    return f"{ds:.1f}"


def render_b30(
    player_name: str,
    rating: float,
    sections: list[tuple[str, list[UnifiedScore]]],
    covers: dict[int, Image.Image],
    *,
    width: int = 760,
    card_h: int = 56,
) -> Image.Image:
    """渲染 CHUNITHM B30 图片。

    Args:
        player_name: 玩家昵称。
        rating: 总 Rating。
        sections: [(分区标题, [UnifiedScore, ...]), ...]，通常为 Best 30 / Selection 10 / New Best 20。
        covers: ``music_id -> PIL.Image`` 封面图。
        width: 图片宽度。
        card_h: 单行卡片高度。
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
    draw.text((pad, 14), sanitize_emoji(f"🎵 {player_name} 的 CHUNITHM Best 30"), font=title_font, fill=(255, 255, 255, 255))
    draw.text((pad, 54), f"Rating: {rating}", font=sub_font, fill=(230, 240, 238, 255))

    y = header_h + pad

    name_font = get_font(15, bold=True)
    small_font = get_font(12)
    meta_font = get_font(13)

    for sec_idx, (sec_title, scores) in enumerate(sections):
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
            draw.text((name_x, top + 6), title, font=name_font, fill=_TITLE)
            draw.text((name_x, top + 30), f"{s.level_label or '?'}  |  定数 {_fmt_ds(s.ds)}", font=small_font, fill=_MUTED)

            # 分数 + 评级
            score_x = width - pad - 250
            draw.text((score_x, top + 8), _fmt_score(s.score), font=meta_font, fill=_ACCENT)
            draw.text((score_x, top + 30), _fmt_rating(s.rating), font=small_font, fill=_MUTED)

            # FC / Chain
            fc_x = width - pad - 130
            fc = CHU_FC_LABELS.get(s.full_combo, "-")
            chain = CHU_CHAIN_LABELS.get(s.full_chain, "")
            fc_text = fc if not chain else f"{fc}/{chain}"
            draw.text((fc_x, top + 8), fc_text, font=small_font, fill=_TEXT)
            draw.text((fc_x, top + 30), "FC", font=small_font, fill=_MUTED)

            # CLEAR
            clear_x = width - pad - 60
            clear = CHU_CLEAR_LABELS.get(s.clear, "-")
            draw.text((clear_x, top + 8), clear, font=get_font(12, bold=True), fill=_TITLE)
            draw.text((clear_x, top + 30), "CLEAR", font=small_font, fill=_MUTED)

            y += card_h

        if sec_idx < len(sections) - 1:
            y += gap

    return img
