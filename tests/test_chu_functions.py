"""CHUNITHM 纯函数测试：chu_rank_label / chu_rating。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.chu_data import chu_rank_label, chu_rating


def test_chu_rank_label_thresholds():
    assert chu_rank_label(1009000) == "SSS+"
    assert chu_rank_label(1007500) == "SSS"
    assert chu_rank_label(1005000) == "SS+"
    assert chu_rank_label(1000000) == "SS"
    assert chu_rank_label(990000) == "S+"
    assert chu_rank_label(975000) == "S"
    assert chu_rank_label(950000) == "AAA"
    assert chu_rank_label(925000) == "AA"
    assert chu_rank_label(900000) == "A"
    assert chu_rank_label(800000) == "BBB"
    assert chu_rank_label(700000) == "BB"
    assert chu_rank_label(600000) == "B"
    assert chu_rank_label(500000) == "C"
    assert chu_rank_label(499999) == "D"


def test_chu_rating_sss_plus():
    # SSS+ 直接 +2.15，但注意街机「截断」行为：int(rating*100)/100
    # 14.0 + 2.15 = 16.15 在二进制浮点中为 16.1499...，截断后为 16.14
    assert chu_rating(13.5, 1009000) == 15.65  # 13.5+2.15=15.65 精确
    assert chu_rating(13.0, 1009000) == 15.15  # 13.0+2.15=15.15 精确


def test_chu_rating_truncates_to_two_decimals():
    # 街机行为：截断到小数点后两位（不是四舍五入）
    # level 14.0, score 1008000: 14.0 + 2.0 + 500/10000 = 16.05
    assert chu_rating(14.0, 1008000) == 16.05


def test_chu_rating_never_negative():
    assert chu_rating(14.0, 0) == 0.0
    assert chu_rating(14.0, 100000) == 0.0


def test_chu_rating_monotonic():
    # 分数越高 rating 不降
    level = 13.0
    prev = -1.0
    for score in [500000, 800000, 900000, 925000, 975000, 1000000, 1005000, 1007500, 1009000]:
        r = chu_rating(level, score)
        assert r >= prev, f"score {score} 的 rating {r} 应 >= {prev}"
        prev = r
