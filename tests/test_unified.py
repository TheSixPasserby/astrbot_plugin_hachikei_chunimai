"""unified 统一成绩模型测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.unified import (
    UnifiedScore,
    lxns_id_to_df,
    df_id_to_lxns,
    from_divingfish_chart,
    from_lxns_maimai,
    from_chunithm,
)


def test_lxns_df_id_mapping():
    # 与代码库既有约定一致：Lxns 4 位 ID < 10000 → DivingFish 5 位 ID +10000
    assert lxns_id_to_df(834) == 10834
    assert lxns_id_to_df(123) == 10123
    # 已经 >= 10000 的保持不变
    assert lxns_id_to_df(10123) == 10123
    # 反向
    assert df_id_to_lxns(10834) == 834
    assert df_id_to_lxns(10123) == 123


def test_from_divingfish_chart():
    class _Chart:
        song_id = 10123
        title = "测试曲"
        level_index = 3
        ds = 13.6
        ra = 14
        type = "dx"
        achievements = 99.5
        dxScore = 100
        rate = "ssp"
        fc = "fc"
        fs = "fs"

    u = from_divingfish_chart(_Chart())
    assert isinstance(u, UnifiedScore)
    assert u.music_id == 10123
    assert u.title == "测试曲"
    assert u.level_label == "MASTER"
    assert u.ds == 13.6
    assert u.rating == 14.0
    assert u.achievements == 99.5


def test_from_lxns_maimai():
    s = {
        "id": 123, "song_name": "DX曲", "level_index": 4,
        "type": "dx", "achievements": 100.5, "dx_score": 5000,
        "dx_rating": 15, "rate": "sssp", "fc": "fcp", "fs": "fsdp",
    }
    u = from_lxns_maimai(s, ds=14.6)
    assert u.music_id == 10123  # 123 -> +10000
    assert u.level_label == "RE:MASTER"
    assert u.ds == 14.6
    assert u.rating == 15.0
    assert u.dx_score == 5000


def test_from_chunithm():
    s = {
        "id": 800, "song_name": "CHU曲", "level_index": 2,
        "rating": 13.45, "score": 1007000,
        "clear": "absolute", "full_combo": "fullcombo", "full_chain": "fullchain",
    }
    u = from_chunithm(s, ds=13.0)
    assert u.music_id == 800
    assert u.level_label == "EXPERT"
    assert u.score == 1007000
    assert u.rating == 13.45
