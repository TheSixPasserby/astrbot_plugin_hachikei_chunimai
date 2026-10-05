"""render.b30 图片渲染测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.unified import UnifiedScore
from astrbot_plugin_hachikei_chunimai.render.b30 import render_b30


def _make(mid: int, title: str, rating: float) -> UnifiedScore:
    return UnifiedScore(
        music_id=mid, title=title, level_index=3, level_label="MASTER",
        ds=13.5, rating=rating, score=1000000, clear="absolute",
        full_combo="fullcombo", full_chain="fullchain",
    )


def test_render_b30_returns_image():
    bests = [_make(800 + i, f"曲{i}", 13.0 + i * 0.1) for i in range(3)]
    img = render_b30("玩家", 15.0, [("Best 30", bests)], {})
    assert img.width > 0
    assert img.height > 200


def test_render_b30_height_grows():
    few = [_make(800 + i, f"曲{i}", 13.0) for i in range(2)]
    many = [_make(800 + i, f"曲{i}", 13.0) for i in range(10)]
    img_few = render_b30("玩家", 100, [("Best 30", few)], {})
    img_many = render_b30("玩家", 100, [("Best 30", many)], {})
    assert img_many.height > img_few.height
