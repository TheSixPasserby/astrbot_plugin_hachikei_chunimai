"""render.b50 图片渲染测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.unified import UnifiedScore
from astrbot_plugin_hachikei_chunimai.render.b50 import render_b50


def _make_score(mid: int, title: str, rating: float) -> UnifiedScore:
    return UnifiedScore(
        music_id=mid, title=title, level_index=3, level_label="MASTER",
        ds=13.0, rating=rating, type="dx", achievements=99.5, rate="ssp", fc="fc",
    )


def test_render_b50_returns_image():
    sd = [_make_score(10000 + i, f"曲{i}", 13.0 + i * 0.1) for i in range(3)]
    dx = [_make_score(11000 + i, f"DX曲{i}", 15.0) for i in range(2)]
    img = render_b50("玩家", 15000, [("SD", sd), ("DX", dx)], {})
    assert img.width > 0
    assert img.height > 200


def test_render_b50_height_grows_with_scores():
    few = [_make_score(10000 + i, f"曲{i}", 13.0) for i in range(2)]
    many = [_make_score(10000 + i, f"曲{i}", 13.0) for i in range(10)]
    img_few = render_b50("玩家", 100, [("SD", few)], {})
    img_many = render_b50("玩家", 100, [("SD", many)], {})
    assert img_many.height > img_few.height
