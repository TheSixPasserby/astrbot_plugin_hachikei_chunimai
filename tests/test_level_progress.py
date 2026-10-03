"""等级进度评价过滤（_rank_threshold）纯函数测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from command.mai_table import _rank_threshold


def test_known_ranks():
    assert _rank_threshold("SSS+") == 100.5
    assert _rank_threshold("sss") == 100.0
    assert _rank_threshold("ss+") == 99.5
    assert _rank_threshold("ss") == 99.0
    assert _rank_threshold("s+") == 98.0
    assert _rank_threshold("s") == 97.0
    assert _rank_threshold("aaa") == 94.0
    assert _rank_threshold("aa") == 90.0
    assert _rank_threshold("a") == 80.0
    assert _rank_threshold("bbb") == 75.0
    assert _rank_threshold("bb") == 70.0
    assert _rank_threshold("b") == 60.0
    assert _rank_threshold("c") == 50.0
    assert _rank_threshold("d") == 0.0


def test_case_insensitive():
    assert _rank_threshold("SSS") == 100.0
    assert _rank_threshold("Sss") == 100.0


def test_whitespace_trimmed():
    assert _rank_threshold("  ss  ") == 99.0


def test_unknown_rank_returns_none():
    assert _rank_threshold("") is None
    assert _rank_threshold("xyz") is None
    assert _rank_threshold("100") is None
