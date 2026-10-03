"""帮助图渲染测试（依赖 Pillow）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.command.help import HELP_SECTIONS, build_help_text
from astrbot_plugin_hachikei_chunimai.render.help import render_help


def test_help_sections_structure():
    # 每个分区都有 emoji/title/commands
    for key, sec in HELP_SECTIONS.items():
        assert sec.get("emoji")
        assert sec.get("title")
        assert isinstance(sec.get("commands"), list)
        for c in sec["commands"]:
            assert "cmd" in c and "desc" in c


def test_build_help_text_contains_all_titles():
    text = build_help_text("maimai", None)
    for key, sec in HELP_SECTIONS.items():
        assert sec["title"] in text


def test_render_help_returns_image():
    img = render_help(HELP_SECTIONS, current_game="maimai", group_game=None)
    assert img.width > 0 and img.height > 0
    # 高度应随分区数量增长（至少 > 页眉）
    assert img.height > 200


def test_render_help_with_group_game():
    img = render_help(HELP_SECTIONS, current_game="chunithm", group_game="maimai")
    assert img.width > 0
