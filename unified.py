"""统一成绩模型：把 DivingFish / Lxns / CHUNITHM 的成绩映射为统一结构。

数据流：:

    查分器 (DivingFish / Lxns / CHUNITHM)
              ↓
        UnifiedScore
              ↓
        Renderer (B50 / B30 / ...)

Renderer 不直接理解任何查分器的字段，只消费 ``UnifiedScore``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# maimai 难度标签（索引 0..4）
MAIMAI_DIFF_LABELS = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"]

# CHUNITHM 难度标签（索引 0..5）
CHU_DIFF_LABELS = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA", "WORLD'S END"]


@dataclass
class UnifiedScore:
    """跨查分器的统一单曲成绩。"""

    music_id: int
    title: str
    level_index: int
    level_label: str = ""
    ds: float | None = None
    rating: float = 0.0
    type: str = ""  # maimai: dx / std；CHUNITHM 无意义

    # --- maimai 字段 ---
    achievements: float | None = None
    dx_score: int | None = None
    rate: str = ""   # 评级标签（SSS+ 等）
    fc: str = ""     # FC 标签（FC / FC+ / AP / AP+ / FDX / FDX+）
    fs: str = ""     # FS 标签（FS / FS+ / SYNC）

    # --- CHUNITHM 字段 ---
    score: int | None = None
    clear: str = ""
    full_combo: str = ""
    full_chain: str = ""


def _maimai_level_label(level_index: int) -> str:
    if 0 <= level_index < len(MAIMAI_DIFF_LABELS):
        return MAIMAI_DIFF_LABELS[level_index]
    return "?"


def _chu_level_label(level_index: int) -> str:
    if 0 <= level_index < len(CHU_DIFF_LABELS):
        return CHU_DIFF_LABELS[level_index]
    return "?"


def lxns_id_to_df(lxns_id: int) -> int:
    """Lxns maimai 4 位 ID → DivingFish 5 位 ID。

    与项目既有约定一致：DX 曲目水鱼 5 位 ID = 落雪 4 位 ID + 10000；
    标准曲目两者 ID 相同（< 10000）。
    """
    return lxns_id + 10000 if lxns_id < 10000 else lxns_id


def df_id_to_lxns(df_id: int) -> int:
    """DivingFish 5 位 ID → Lxns 4 位 ID（封面下载等场景使用）。"""
    return df_id - 10000 if df_id >= 10000 else df_id


def from_divingfish_chart(c: Any, *, ds: float | None = None) -> UnifiedScore:
    """DivingFish ``ChartInfo`` → ``UnifiedScore``。"""
    return UnifiedScore(
        music_id=int(c.song_id),
        title=c.title,
        level_index=c.level_index,
        level_label=_maimai_level_label(c.level_index),
        ds=ds if ds is not None else (c.ds or None),
        rating=float(getattr(c, "ra", 0) or 0),
        type=getattr(c, "type", ""),
        achievements=float(c.achievements),
        dx_score=int(getattr(c, "dxScore", 0) or 0),
        rate=getattr(c, "rate", "") or "",
        fc=getattr(c, "fc", "") or "",
        fs=getattr(c, "fs", "") or "",
    )


def from_lxns_maimai(s: dict, *, ds: float | None = None) -> UnifiedScore:
    """Lxns maimai bests 条目（dict）→ ``UnifiedScore``。"""
    lxns_id = int(s.get("id", 0))
    df_id = lxns_id_to_df(lxns_id)
    return UnifiedScore(
        music_id=df_id,
        title=s.get("song_name", ""),
        level_index=int(s.get("level_index", 3)),
        level_label=_maimai_level_label(int(s.get("level_index", 3))),
        ds=ds,
        rating=float(s.get("dx_rating") or s.get("rating") or 0),
        type=s.get("type", ""),
        achievements=float(s.get("achievements", 0) or 0),
        dx_score=int(s.get("dx_score", 0) or 0),
        rate=s.get("rate", "") or "",
        fc=s.get("fc", "") or "",
        fs=s.get("fs", "") or "",
    )


def from_chunithm(s: dict, *, ds: float | None = None) -> UnifiedScore:
    """Lxns CHUNITHM bests 条目（dict）→ ``UnifiedScore``。"""
    level_index = int(s.get("level_index", 3))
    return UnifiedScore(
        music_id=int(s.get("id", 0)),
        title=s.get("song_name", ""),
        level_index=level_index,
        level_label=_chu_level_label(level_index),
        ds=ds,
        rating=float(s.get("rating", 0) or 0),
        score=int(s.get("score", 0) or 0),
        clear=s.get("clear", "") or "",
        full_combo=s.get("full_combo", "") or "",
        full_chain=s.get("full_chain", "") or "",
    )
