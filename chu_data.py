"""CHUNITHM 数据管理：歌曲数据加载、查询、Rating 计算。"""

from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path
from typing import Any

from .lxns_client import LxnsAPI

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# --- CHUNITHM 常量 ---

CHU_LEVEL_LIST = [
    "1", "2", "3", "4", "5", "6", "7", "7+", "8", "8+",
    "9", "9+", "10", "10+", "11", "11+", "12", "12+", "13", "13+",
    "14", "14+", "15",
]

CHU_DIFF_LABELS = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA", "WORLD'S END"]
CHU_DIFF_INDEX = {label: i for i, label in enumerate(CHU_DIFF_LABELS)}

# [修正] 更新为 CHUNITHM NEW 以后的正确分数线
CHU_RANK_THRESHOLDS = [
    (1009000, "SSS+"), (1007500, "SSS"), (1005000, "SS+"), (1000000, "SS"),
    (990000, "S+"), (975000, "S"), (950000, "AAA"), (925000, "AA"),
    (900000, "A"), (800000, "BBB"), (700000, "BB"), (600000, "B"),
    (500000, "C"), (0, "D"),
]

CHU_CLEAR_LABELS = {
    "catastrophy": "CATASTROPHY", "absolute": "ABSOLUTE", "brave": "BRAVE",
    "hard": "HARD", "clear": "CLEAR", "failed": "FAILED",
}

CHU_FC_LABELS = {
    "alljusticecritical": "AJC", "alljustice": "AJ", "fullcombo": "FC",
}

CHU_CHAIN_LABELS = {
    "fullchain": "铂FC", "fullchain2": "金FC",
}


def chu_rank_label(score: int) -> str:
    for threshold, label in CHU_RANK_THRESHOLDS:
        if score >= threshold:
            return label
    return "D"


def chu_rating(level_value: float, score: int) -> float:
    """计算 CHUNITHM 单曲 Rating (更新至 CHUNITHM NEW+ 现行标准)。"""
    if score >= 1009000:
        rating = level_value + 2.15
    elif score >= 1007500:
        rating = level_value + 2.0 + (score - 1007500) / 10000
    elif score >= 1005000:
        rating = level_value + 1.5 + (score - 1005000) / 5000
    elif score >= 1000000:
        rating = level_value + 1.0 + (score - 1000000) / 10000
    elif score >= 975000:
        rating = level_value + (score - 975000) / 25000
    elif score >= 925000:
        rating = level_value - 3.0 + (score - 925000) / 50000 * 3.0
    elif score >= 900000:
        rating = level_value - 5.0 + (score - 900000) / 25000 * 2.0
    elif score >= 800000:
        half = (level_value - 5.0) / 2
        rating = half + (score - 800000) / 100000 * half
    elif score >= 500000:
        rating = (score - 500000) / 300000 * ((level_value - 5.0) / 2)
    else:
        rating = 0.0

    # 街机游戏中 Rating 计算截断保留到小数点后两位
    return max(0.0, int(rating * 100) / 100.0)


# --- 数据类 ---

class ChuSong:
    """CHUNITHM 歌曲数据。"""
    __slots__ = ("id", "title", "artist", "genre", "bpm", "version", "difficulties", "disabled")

    def __init__(self, data: dict) -> None:
        # 兼容 Lxns API 可能将 id 视作字符串或整型的情况
        self.id: int = int(data.get("id", 0))
        self.title: str = data.get("title", "")
        self.artist: str = data.get("artist", "")
        self.genre: str = data.get("genre", "")
        self.bpm: int = data.get("bpm", 0)
        self.version: int = data.get("version", 0)
        self.disabled: bool = data.get("disabled", False)
        self.difficulties: list[dict] = data.get("difficulties", [])

    def get_level(self, idx: int) -> str | None:
        for d in self.difficulties:
            if d.get("difficulty") == idx:
                return d.get("level")
        return None

    def get_level_value(self, idx: int) -> float | None:
        for d in self.difficulties:
            if d.get("difficulty") == idx:
                return d.get("level_value")
        return None


class ChuDataManager:
    """CHUNITHM 数据管理器。"""

    def __init__(self, lxns: LxnsAPI, data_dir: Path) -> None:
        self.lxns = lxns
        self._dir = data_dir / "chunithm"
        self._dir.mkdir(parents=True, exist_ok=True)
        self.songs: dict[int, ChuSong] = {}
        self.aliases: dict[int, list[str]] = {}

    async def _read_json(self, name: str) -> dict | None:
        p = self._dir / name
        if not p.exists():
            return None
        try:
            return await asyncio.to_thread(lambda: json.loads(p.read_text("utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取本地缓存 {name} 失败: {e}")
            return None

    async def _write_json(self, name: str, data: Any) -> None:
        p = self._dir / name
        try:
            await asyncio.to_thread(
                lambda: p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
            )
        except OSError as e:
            logger.error(f"写入本地缓存 {name} 失败: {e}")

    async def load_songs(self) -> None:
        """从 Lxns 加载歌曲数据。"""
        data = None
        try:
            raw_data = await self.lxns.chu_song_list()
            await self._write_json("songs.json", raw_data)
            data = raw_data
        except Exception as e:
            logger.warning(f"从 Lxns 获取 CHUNITHM 歌曲失败 ({e})，尝试本地缓存")
            data = await self._read_json("songs.json")

        if not data:
            logger.error("无 CHUNITHM 歌曲数据缓存可加载。")
            return

        # [修正] 兼容标准 API 响应 wrapper `{"success": true, "data": [...]}`
        song_list = data.get("data", data.get("songs", [])) if isinstance(data, dict) else data

        self.songs = {}
        for s in song_list:
            song = ChuSong(s)
            self.songs[song.id] = song
        logger.info(f"CHUNITHM: 加载了 {len(self.songs)} 首歌曲")

    async def load_aliases(self) -> None:
        """从 Lxns 加载别名数据。"""
        data = None
        try:
            raw_data = await self.lxns.chu_alias_list()
            await self._write_json("aliases.json", raw_data)
            data = raw_data
            logger.info("从落雪获取 CHUNITHM 别名成功")
        except Exception as e:
            logger.warning(f"从落雪获取 CHUNITHM 别名失败: {e}，尝试本地缓存")
            data = await self._read_json("aliases.json")

        if not data:
            return

        # [修正] 同样兼容 wrapper，以及字典中可能是 song_id 或 id
        alias_list = data.get("data", data.get("aliases", [])) if isinstance(data, dict) else data

        self.aliases = {}
        for a in alias_list:
            song_id = int(a.get("song_id", a.get("id", 0)))
            if song_id:
                self.aliases[song_id] = a.get("aliases", [])
        logger.info(f"CHUNITHM: 加载了 {len(self.aliases)} 条别名")

    async def load_all(self) -> None:
        await self.load_songs()
        await self.load_aliases()

    def find_by_keyword(self, keyword: str) -> list[ChuSong]:
        """[修正] 优化了匹配算法，使用 dict(ID作为key) 防止出现大量重复查询"""
        kw = keyword.lower()
        results: dict[int, ChuSong] = {}

        # 1. 标题与曲师匹配
        for song in self.songs.values():
            if kw in song.title.lower() or kw in song.artist.lower():
                results[song.id] = song

        # 2. 别名匹配 (跳过已经匹配成功的歌曲)
        for sid, aliases in self.aliases.items():
            if sid in results:
                continue
            if any(kw in a.lower() for a in aliases):
                song = self.songs.get(sid)
                if song:
                    results[song.id] = song

        return list(results.values())

    def find_by_id(self, song_id: int | str) -> ChuSong | None:
        try:
            return self.songs.get(int(song_id))
        except (ValueError, TypeError):
            return None

    def random_song(self, level: str | None = None) -> ChuSong | None:
        candidates = [s for s in self.songs.values() if not s.disabled]
        if level:
            candidates = [s for s in candidates if any(d.get("level") == level for d in s.difficulties)]
        return secrets.choice(candidates) if candidates else None

    def get_aliases(self, song_id: int) -> list[str]:
        return self.aliases.get(song_id, [])
