"""command.fun 趣味功能测试（不依赖 AstrBot）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.command.fun import (
    _FORTUNES,
    daily_fortune_handler,
    mai_what_handler,
    random_song_handler,
)


def test_fortunes_non_empty():
    assert len(_FORTUNES) == 5
    assert all(label and text for label, text in _FORTUNES)


def test_fortunes_deterministic():
    # daily_fortune_handler 内部按 qq+日期 做种子，这里只验证同一种子稳定
    import random
    r1 = random.Random(12345).choice(_FORTUNES)
    r2 = random.Random(12345).choice(_FORTUNES)
    assert r1 == r2
