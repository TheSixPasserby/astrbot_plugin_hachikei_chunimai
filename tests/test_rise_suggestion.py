"""推分建议 _rise_suggestion 纯函数测试（无外部依赖）。

验证根因修复：成绩必须匹配 song_id + level_index，
不能用某首歌的达成率去套另一难度/另一首歌的定数。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.command.mai_table import _rise_suggestion
from astrbot_plugin_hachikei_chunimai.mai_data import MusicDataManager


class _Chart:
    """最小成绩对象，字段与 handler 内匿名对象一致。"""
    def __init__(self, song_id, level_index, achievements, ra, title):
        self.song_id = song_id
        self.level_index = level_index
        self.achievements = achievements
        self.ra = ra
        self.title = title


class _Music:
    """最小歌曲对象，仅暴露 ds / level / id 字段。"""
    def __init__(self, id_, ds, level):
        self.id = str(id_)
        self.ds = ds
        self.level = level


def _music(ds, level):
    return _Music(1, ds, level)


def test_level_index_locked_not_other_difficulty():
    # 玩家只在 MASTER(索引 3) 有成绩，但 MASTER 定数与 EXPERT(索引 2) 不同
    # 修复前会遍历所有 ds，把 EXPERT 的定数套到 MASTER 成绩上
    music = _music(
        ds=[8.0, 9.0, 10.0, 13.6, 0.0],
        level=["1", "2", "3", "4", "5"],
    )
    # 真实 old_ra = compute_ra(13.6, 98.0) = 13；+1.0 后 99.0 → 14
    chart = _Chart("1", level_index=3, achievements=98.0, ra=13, title="Song")
    sug = _rise_suggestion(chart, music, level=None)
    # 新 Ra 必须基于 ds[3]=13.6，而不是 ds[0..2]
    assert sug is not None
    gain, title, lv, old_ra, new_ra = sug
    expected_new_ra = MusicDataManager.compute_ra(13.6, 99.0)
    assert new_ra == expected_new_ra
    assert new_ra == 14  # int(13.6 + 0.5) = 14，与 ds[0..2] 的 8/9/10 无关


def test_out_of_range_level_index_returns_none():
    music = _music(ds=[10.0, 11.0, 12.0, 13.0], level=["1", "2", "3", "4"])
    chart = _Chart("1", level_index=9, achievements=99.0, ra=100, title="Song")
    assert _rise_suggestion(chart, music, level=None) is None


def test_negative_level_index_returns_none():
    music = _music(ds=[10.0], level=["1"])
    chart = _Chart("1", level_index=-1, achievements=99.0, ra=100, title="Song")
    assert _rise_suggestion(chart, music, level=None) is None


def test_level_filter_applied_after_lock():
    # level 过滤针对锁定难度；锁定难度不符合 level 时返回 None
    music = _music(ds=[10.0, 12.0], level=["10", "12"])
    # 真实 old_ra = compute_ra(12.0, 99.0) = 12
    chart = _Chart("1", level_index=1, achievements=99.0, ra=12, title="Song")
    assert _rise_suggestion(chart, music, level="10") is None  # 锁定 idx=1 是 "12"，非 "10"
    assert _rise_suggestion(chart, music, level="12") is not None


def test_no_suggestion_when_new_ra_not_higher():
    music = _music(ds=[13.6], level=["13+"])
    chart = _Chart("1", level_index=0, achievements=100.5, ra=100, title="Song")
    # 达成率 100.5 已是 SSS+ 峰值，+1.0 不提升 Ra
    assert _rise_suggestion(chart, music, level=None) is None


def test_song_not_found_handled_by_caller():
    # by_id 返回 None 由调用方跳过；此处仅确认 helper 不抛异常
    # （无对应测试对象，用越界难度代表「无有效谱面」场景）
    music = _music(ds=[], level=[])
    chart = _Chart("1", level_index=0, achievements=99.0, ra=100, title="Song")
    assert _rise_suggestion(chart, music, level=None) is None
