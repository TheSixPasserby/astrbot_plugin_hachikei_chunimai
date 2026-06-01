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

CHU_RANK_THRESHOLDS = [
    (1007500, "SSS+"), (1000000, "SSS"), (990000, "SS+"), (975000, "SS"),
    (950000, "S+"), (925000, "S"), (900000, "AAA"), (800000, "AA"),
    (700000, "A"), (600000, "BBB"), (500000, "BB"), (400000, "B"),
    (300000, "C"), (0, "D"),
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
    """计算 CHUNITHM 单曲 Rating。"""
    if score >= 1007500:
        return level_value + 2.0
    if score >= 1005000:
        return level_value + 1.5 + (score - 1000000) / 10000 * 0.5
    if score >= 1000000:
        return level_value + 1.5
    if score >= 990000:
        return level_value + 1.0 + (score - 990000) / 10000 * 0.5
    if score >= 975000:
        return level_value + 0.5 + (score - 975000) / 15000 * 0.5
    if score >= 950000:
        return level_value + (score - 950000) / 25000 * 0.5
    if score >= 925000:
        return level_value - 1.0 + (score - 925000) / 25000 * 1.0
    if score >= 900000:
        return level_value - 3.0 + (score - 900000) / 25000 * 2.0
    if score >= 800000:
        return level_value - 5.0 + (score - 800000) / 100000 * 2.0
    if score >= 700000:
        return max(level_value - 7.0 + (score - 700000) / 100000 * 2.0, 0)
    if score >= 600000:
        return max(level_value - 9.0 + (score - 600000) / 100000 * 2.0, 0)
    if score >= 500000:
        return max(level_value - 11.0 + (score - 500000) / 100000 * 2.0, 0)
    if score >= 400000:
        return max(level_value - 13.0 + (score - 400000) / 100000 * 2.0, 0)
    if score >= 300000:
        return max(level_value - 15.0 + (score - 300000) / 100000 * 2.0, 0)
    return 0.0


# --- 数据类 ---

class ChuSong:
    """CHUNITHM 歌曲数据。"""
    __slots__ = ("id", "title", "artist", "genre", "bpm", "version", "difficulties", "disabled")

    def __init__(self, data: dict) -> None:
        self.id: int = data["id"]
        self.title: str = data["title"]
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

    async def _read_json(self, name: str) -> Any:
        p = self._dir / name
        try:
            return await asyncio.to_thread(lambda: json.loads(p.read_text("utf-8")))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return None

    async def _write_json(self, name: str, data: Any) -> None:
        p = self._dir / name
        await asyncio.to_thread(
            lambda: p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        )

    async def load_songs(self) -> None:
        """从 Lxns 加载歌曲数据。"""
        try:
            data = await self.lxns.chu_song_list()
            await self._write_json("songs.json", data)
        except Exception:
            logger.warning("从 Lxns 获取 CHUNITHM 歌曲失败，尝试本地缓存")
            data = await self._read_json("songs.json")
            if not data:
                logger.error("无 CHUNITHM 歌曲数据缓存")
                return

        self.songs = {}
        for s in data.get("songs", []):
            song = ChuSong(s)
            self.songs[song.id] = song
        logger.info(f"CHUNITHM: 加载了 {len(self.songs)} 首歌曲")

    async def load_aliases(self) -> None:
        """从 Lxns 加载别名数据。"""
        try:
            data = await self.lxns.chu_alias_list()
            await self._write_json("aliases.json", data)
        except Exception:
            logger.warning("从 Lxns 获取 CHUNITHM 别名失败，尝试本地缓存")
            data = await self._read_json("aliases.json")
            if not data:
                return

        self.aliases = {}
        for a in data.get("aliases", []):
            self.aliases[a["song_id"]] = a.get("aliases", [])
        logger.info(f"CHUNITHM: 加载了 {len(self.aliases)} 条别名")

    async def load_all(self) -> None:
        await self.load_songs()
        await self.load_aliases()

    def find_by_keyword(self, keyword: str) -> list[ChuSong]:
        kw = keyword.lower()
        results = []
        for song in self.songs.values():
            if kw in song.title.lower() or kw in song.artist.lower():
                results.append(song)
        # 别名匹配
        for sid, aliases in self.aliases.items():
            if any(kw in a.lower() for a in aliases):
                song = self.songs.get(sid)
                if song and song not in results:
                    results.append(song)
        return results

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
