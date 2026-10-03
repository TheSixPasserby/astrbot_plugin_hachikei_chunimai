"""render.emoji 单色符号回退测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.render.emoji import sanitize_emoji


def test_maps_known_emoji_to_symbols():
    text = "🎵 📊 🔍 🎮 📋 🏷️ 🎲 ⭐"
    out = sanitize_emoji(text)
    assert "♪" in out
    assert "≡" in out
    assert "◎" in out
    assert "▶" in out
    assert "■" in out
    assert "◆" in out
    assert "●" in out
    assert "★" in out


def test_removes_astral_plane_emoji():
    # 未在映射中的多字节平面 emoji（U+1F600）应被清除
    out = sanitize_emoji("😀测试")
    assert out == "测试"


def test_removes_variation_selectors():
    out = sanitize_emoji("☑\ufe0f")
    # ☑ 位于 BMP，变体选择符被移除后应保留
    assert "\ufe0f" not in out


def test_plain_text_unchanged():
    assert sanitize_emoji("普通文本 123") == "普通文本 123"


def test_empty_string():
    assert sanitize_emoji("") == ""
