"""Emoji -> 单色符号回退。

Pillow 用 CJK 字体（如 Noto Sans CJK / STHeiti / 微软雅黑）渲染彩色 emoji
时会显示为方框（豆腐块），因为这类字体不含彩色 emoji 字形。

渲染图片前，先把已知 emoji 替换成 CJK 字体普遍覆盖的单色符号，再移除
剩余的多字节平面（astral plane）字符与变体选择符，保证图片中不出现豆腐块。
"""

from __future__ import annotations

# emoji -> 单色符号。符号均选自常见 CJK 字体（Noto Sans CJK / STHeiti / 微软雅黑）
# 确定覆盖的 Geometric Shapes / Misc Symbols / Dingbats 区块。
_EMOJI_MAP: dict[str, str] = {
    # 音乐
    "🎵": "♪",
    "🎶": "♫",
    "🎼": "♫",
    "🎧": "♫",
    # 图表 / 数据
    "📊": "≡",
    "📈": "▲",
    "📉": "▼",
    # 搜索
    "🔍": "◎",
    "🔎": "◎",
    # 游戏 / 娱乐
    "🎮": "▶",
    "🎲": "●",
    "🎯": "◎",
    # 标签 / 列表 / 文档
    "🏷️": "◆",
    "📋": "■",
    "📝": "■",
    "📄": "■",
    # 星星
    "⭐": "★",
    "🌟": "★",
    "✨": "★",
    # 其他常用
    "✅": "√",
    "❌": "×",
    "⚠️": "!",
    "ℹ️": "i",
    "❤️": "♥",
    "💔": "◇",
    "🔒": "◆",
    "🔓": "◇",
    "⚙️": "◇",
    "🔧": "◇",
}

_VARIATION_SELECTORS = ("\ufe0f", "\ufe0e")


def sanitize_emoji(text: str) -> str:
    """把字符串里的彩色 emoji 替换为单色符号，并清除剩余的 emoji 平面字符。

    对无 emoji 的字符串原样返回（不产生额外开销）。
    """
    if not text:
        return text

    for emoji, symbol in _EMOJI_MAP.items():
        if emoji in text:
            text = text.replace(emoji, symbol)

    # 移除变体选择符
    for vs in _VARIATION_SELECTORS:
        text = text.replace(vs, "")

    # 移除映射未覆盖的多字节平面字符（绝大多数彩色 emoji 位于该平面）
    # 以及 BMP 内的 emoji 专用区段（U+1F000+ 已是 astral，U+2600 等保留单色符号）
    cleaned = "".join(ch for ch in text if ord(ch) <= 0xFFFF)
    return cleaned
