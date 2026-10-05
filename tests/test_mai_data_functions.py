"""mai_data 纯函数测试：achievements_label / compute_ra / cross / in_or_equal。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.mai_data import (
    achievements_label, cross, in_or_equal, MusicDataManager,
)


def test_achievements_label_thresholds():
    assert achievements_label(100.5) == "SSS+"
    assert achievements_label(100.0) == "SSS"
    assert achievements_label(99.5) == "SS+"
    assert achievements_label(99.0) == "SS"
    assert achievements_label(98.0) == "S+"
    assert achievements_label(97.0) == "S"
    assert achievements_label(94.0) == "AAA"
    assert achievements_label(90.0) == "AA"
    assert achievements_label(80.0) == "A"
    assert achievements_label(75.0) == "BBB"
    assert achievements_label(70.0) == "BB"
    assert achievements_label(60.0) == "B"
    assert achievements_label(50.0) == "C"
    assert achievements_label(49.99) == "D"


def test_compute_ra_basic():
    compute_ra = MusicDataManager.compute_ra
    # 峰值 SSS+
    assert compute_ra(13.6, 100.5) == 15  # 13.6 + 2.0 = 15.6 -> int 15
    # SSS
    assert compute_ra(13.6, 100.0) == 15  # 13.6 + 1.5 = 15.1 -> int 15
    # SS+
    assert compute_ra(13.6, 99.5) == 14  # 13.6 + 1.0 = 14.6 -> int 14
    # SS
    assert compute_ra(13.6, 99.0) == 14  # 13.6 + 0.5 = 14.1 -> int 14
    # S+
    assert compute_ra(13.6, 98.0) == 13  # 13.6 -> int 13
    # S
    assert compute_ra(13.6, 97.0) == 13  # 13.6 - 0.5 = 13.1 -> int 13
    # AAA
    assert compute_ra(13.6, 94.0) == 12  # 13.6 - 1.0 = 12.6 -> int 12
    # 低分
    assert compute_ra(13.6, 40.0) == 0


def test_compute_ra_never_negative():
    compute_ra = MusicDataManager.compute_ra
    assert compute_ra(5.0, 30.0) == 0
    assert compute_ra(3.0, 0.0) == 0


def test_cross_exact_match():
    # checker 是难度列表，elem 是目标值
    ret, diffs = cross(["1", "2", "3", "4"], "3", [0, 1, 2, 3])
    assert ret is True
    assert diffs == [2]


def test_cross_list_match():
    ret, diffs = cross(["1", "2", "3", "4"], ["2", "4"], [0, 1, 2, 3])
    assert ret is True
    assert diffs == [1, 3]


def test_cross_tuple_range():
    ret, diffs = cross([10.0, 11.0, 12.0, 13.0], (11.0, 12.5), [0, 1, 2, 3])
    assert ret is True
    assert diffs == [1, 2]


def test_cross_empty_elem_returns_all():
    ret, diffs = cross(["1", "2"], "", [0, 1])
    assert ret is True
    assert diffs == [0, 1]


def test_in_or_equal():
    assert in_or_equal("a", "a") is True
    assert in_or_equal("a", ["a", "b"]) is True
    assert in_or_equal("c", ["a", "b"]) is False
    assert in_or_equal(11.5, (11.0, 12.0)) is True
    assert in_or_equal(13.0, (11.0, 12.0)) is False
    assert in_or_equal("x", ...) is True
