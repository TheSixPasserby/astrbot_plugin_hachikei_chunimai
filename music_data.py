"""歌曲数据管理：加载、过滤、别名、猜歌逻辑。"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from .api_client import MaimaiAPI
from .models import Alias, Music, RaMusic, Stats

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class MusicList(list):
    """歌曲列表，支持按 ID/标题查询和过滤。"""

    def by_id(self, music_id: int | str) -> Music | None:
        for m in self:
            if m.id == str(music_id):
                return m
        return None

    def by_title(self, title: str) -> Music | None:
        for m in self:
            if m.title == title:
                return m
        return None


# --- 常量 ---

LEVEL_LIST = [
    "1", "2", "3", "4", "5", "6", "7", "7+", "8", "8+",
    "9", "9+", "10", "10+", "11", "11+", "12", "12+", "13", "13+", "14", "14+", "15",
]

DIFF_LABEL_TO_INDEX = {"绿": 0, "黄": 1, "红": 2, "紫": 3, "白": 4}
DIFF_INDEX_TO_LABEL = {v: k for k, v in DIFF_LABEL_TO_INDEX.items()}

achievements_list = [
    (100.5, "SSS+"), (100.0, "SSS"), (99.5, "SS+"), (99.0, "SS"),
    (98.0, "S+"), (97.0, "S"), (94.0, "AAA"), (90.0, "AA"),
    (80.0, "A"), (75.0, "BBB"), (70.0, "BB"), (60.0, "B"), (50.0, "C"), (0.0, "D"),
]


def achievements_label(achievements: float) -> str:
    for threshold, label in achievements_list:
        if achievements >= threshold:
            return label
    return "D"


# --- 辅助函数 ---

def cross(
    checker: list[str] | list[float],
    elem: str | float | list[str] | list[float] | tuple[float, float] | None,
    diff: list[int],
) -> tuple[bool, list[int]]:
    ret = False
    diff_ret = []
    if not elem or elem is Ellipsis:
        return True, diff
    if isinstance(elem, list):
        for j in (range(len(checker)) if diff is Ellipsis else diff):
            if j >= len(checker):
                continue
            if checker[j] in elem:
                diff_ret.append(j)
                ret = True
    elif isinstance(elem, tuple):
        for j in (range(len(checker)) if diff is Ellipsis else diff):
            if j >= len(checker):
                continue
            if elem[0] <= checker[j] <= elem[1]:
                diff_ret.append(j)
                ret = True
    else:
        for j in (range(len(checker)) if diff is Ellipsis else diff):
            if j >= len(checker):
                continue
            if checker[j] == elem:
                diff_ret.append(j)
                ret = True
    return ret, diff_ret


def in_or_equal(checker: Any, elem: Any) -> bool:
    if elem is Ellipsis:
        return True
    if isinstance(elem, list):
        return checker in elem
    if isinstance(elem, tuple):
        return elem[0] <= checker <= elem[1]
    return checker == elem


def search_charts(checker: list, elem: str, diff: list[int]) -> tuple[bool, list[int]]:
    ret = False
    diff_ret = []
    if not elem or elem is Ellipsis:
        return True, diff
    for j in (range(len(checker)) if diff is Ellipsis else diff):
        if elem.lower() in checker[j].charter.lower():
            diff_ret.append(j)
            ret = True
    return ret, diff_ret


# --- MusicList 扩展 ---

def music_by_plan(
    music_list: MusicList, level: str
) -> dict[str, dict]:
    lv: dict = defaultdict(dict)

    def create_ra_music(music: Music, index: int) -> RaMusic:
        return RaMusic(
            id=music.id, ds=music.ds[index],
            lv=str(index), lvp=music.level[index], type=music.type,
        )

    for music in music_list:
        if level not in music.level or int(music.id) >= 100000:
            continue
        if music.level.count(level) > 1:
            lv[music.id] = {
                i: create_ra_music(music, i)
                for i, _lv in enumerate(music.level) if _lv == level
            }
        else:
            index = music.level.index(level)
            lv[music.id] = create_ra_music(music, index)
    return dict(lv)


def music_by_level_list(music_list: MusicList) -> dict[str, dict[str, list[RaMusic]]]:
    def level_range(lv: str) -> range:
        if lv == "15":
            return range(1)
        if lv.endswith("+"):
            return range(9, 5, -1)
        return range(9, -1, -1) if int(lv) <= 5 else range(5, -1, -1)

    level_data = {
        lv: {f"{lv.rstrip('+')}.{i}": [] for i in level_range(lv)}
        for lv in LEVEL_LIST
    }
    for music in music_list:
        if int(music.id) >= 100000:
            continue
        for index, ds in enumerate(music.ds):
            if ds < 7:
                continue
            ra = RaMusic(
                id=music.id, ds=ds, lv=str(index),
                lvp=music.level[index], type=music.type,
            )
            level_data[music.level[index]][str(ds)].append(ra)
    return level_data


def filter_music(
    music_list: MusicList,
    *,
    level: Any = ...,
    ds: Any = ...,
    title_search: str | None = ...,
    artist_search: str | None = ...,
    charter_search: str | None = ...,
    genre: Any = ...,
    bpm: Any = ...,
    type: Any = ...,
    diff: list[int] = ...,
    version: Any = ...,
) -> MusicList:
    new_list = MusicList()
    for music in music_list:
        diff2 = diff
        music = deepcopy(music)
        ret, diff2 = cross(music.level, level, diff2)
        if not ret:
            continue
        ret, diff2 = cross(music.ds, ds, diff2)
        if not ret:
            continue
        ret, diff2 = search_charts(music.charts, charter_search, diff2)
        if not ret:
            continue
        if not in_or_equal(music.basic_info.genre, genre):
            continue
        if not in_or_equal(music.type, type):
            continue
        if not in_or_equal(music.basic_info.bpm, bpm):
            continue
        if not in_or_equal(music.basic_info.version, version):
            continue
        if title_search is not Ellipsis and title_search.lower() not in music.title.lower():
            continue
        if artist_search is not Ellipsis and artist_search.lower() not in music.basic_info.artist.lower():
            continue
        music.diff = diff2
        new_list.append(music)
    return new_list


# --- 别名管理 ---

class AliasList(list):
    """别名列表，支持按 ID 或别名查询。"""

    def by_id(self, music_id: int | str) -> list[Alias]:
        mid = int(music_id)
        return [a for a in self if a.SongID == mid]

    def by_alias(self, alias_name: str) -> list[Alias]:
        return [a for a in self if alias_name in a.Alias]


# --- 猜歌数据 ---

class GuessManager:
    """管理猜歌游戏状态。"""

    def __init__(self) -> None:
        self.active: dict[str, GuessData] = {}  # group_id -> GuessData

    def is_active(self, group_id: str) -> bool:
        return group_id in self.active

    def get(self, group_id: str) -> GuessData | None:
        return self.active.get(group_id)

    def set(self, group_id: str, data: GuessData) -> None:
        self.active[group_id] = data

    def end(self, group_id: str) -> None:
        self.active.pop(group_id, None)


# --- 数据管理器 ---

class MusicDataManager:
    """集中管理所有歌曲、别名、猜歌数据。"""

    def __init__(self, api: MaimaiAPI, data_dir: Path) -> None:
        self.api = api
        self._lxns: Any = None  # 可选：LxnsAPI 实例
        self._alias_source: str = "yuzuchan"  # yuzuchan | lxns
        self._data_dir = data_dir
        self._static_dir = data_dir / "static"
        self._static_dir.mkdir(parents=True, exist_ok=True)

        self.music_list: MusicList = MusicList()
        self.chart_stats: dict = {}
        self.alias_list: AliasList = AliasList()
        self.plate_data: dict[str, list[int]] = {}
        self.level_data: dict[str, dict[str, list[RaMusic]]] = {}
        self.guess_data: list[Music] = []
        self.guess_manager = GuessManager()

    async def _read_json(self, filename: str) -> Any:
        path = self._static_dir / filename
        if not path.exists():
            return None
        try:
            return await asyncio.to_thread(
                lambda: json.loads(path.read_text("utf-8"))
            )
        except (json.JSONDecodeError, OSError):
            return None

    async def _write_json(self, filename: str, data: Any) -> None:
        path = self._static_dir / filename
        await asyncio.to_thread(
            lambda: path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        )

    async def load_music_data(self) -> None:
        """加载歌曲数据和谱面统计。"""
        # 歌曲数据
        try:
            music_data = await self.api.music_data()
            await self._write_json("music_data.json", music_data)
        except Exception:
            logger.warning("从 API 获取歌曲数据失败，尝试本地缓存")
            music_data = await self._read_json("music_data.json")
            if music_data is None:
                logger.error("无本地歌曲数据缓存，请手动下载 music_data.json")
                return

        # 谱面统计
        try:
            self.chart_stats = await self.api.chart_stats()
            await self._write_json("music_chart.json", self.chart_stats)
        except Exception:
            logger.warning("从 API 获取谱面统计失败，尝试本地缓存")
            self.chart_stats = await self._read_json("music_chart.json") or {}

        # 合并数据
        charts = self.chart_stats.get("charts", {})
        self.music_list = MusicList()
        for m in music_data:
            stats_raw = charts.get(m["id"])
            stats = None
            if stats_raw:
                stats = [
                    Stats.model_validate(s) if s and s != {} else None
                    for s in stats_raw
                ] if isinstance(stats_raw, list) and {} in stats_raw else stats_raw
            self.music_list.append(Music(stats=stats, **m))

        self.level_data = music_by_level_list(self.music_list)
        logger.info(f"加载了 {len(self.music_list)} 首歌曲")

    def configure_alias(self, source: str = "yuzuchan", lxns: Any = None) -> None:
        """设置别名数据源。"""
        self._alias_source = source
        self._lxns = lxns

    async def load_alias_data(self) -> None:
        """加载别名数据。"""
        local_alias = await self._read_json("local_alias.json") or {}

        raw_alias: list = []
        if self._alias_source == "lxns" and self._lxns:
            try:
                data = await self._lxns.mai_alias_list()
                for entry in data.get("aliases", []):
                    sid = str(entry.get("song_id", ""))
                    raw_alias.append({"SongID": sid, "Name": "", "Alias": entry.get("aliases", [])})
                await self._write_json("music_alias.json", raw_alias)
                logger.info("从落雪获取舞萌别名成功")
            except Exception as e:
                logger.warning(f"从落雪获取舞萌别名失败: {e}，尝试本地缓存")
                raw_alias = await self._read_json("music_alias.json") or []
        else:
            try:
                raw_alias = await self.api.get_alias()
                await self._write_json("music_alias.json", raw_alias)
            except Exception:
                logger.warning("从柚子获取别名失败，尝试本地缓存")
                raw_alias = await self._read_json("music_alias.json") or []

        self.alias_list = AliasList()
        for a in raw_alias:
            if not self.music_list.by_id(a["SongID"]):
                continue
            song_id_str = str(a["SongID"])
            if song_id_str in local_alias:
                a["Alias"].extend(local_alias[song_id_str])
            self.alias_list.append(Alias.model_validate(a))

        logger.info(f"加载了 {len(self.alias_list)} 条别名")

    async def load_plate_data(self) -> None:
        """加载牌子数据。"""
        try:
            self.plate_data = await self.api.get_plate_json()
        except Exception:
            logger.warning("获取牌子数据失败")

    async def load_all(self) -> None:
        """加载所有数据。"""
        await self.load_music_data()
        await self.load_alias_data()
        await self.load_plate_data()
        self._init_guess_data()

    def _init_guess_data(self) -> None:
        """初始化猜歌数据（播放次数 > 10000 的热门歌曲）。"""
        hot_ids = []
        for music in self.music_list:
            if music.stats:
                total = sum(s.cnt for s in music.stats if s and s.cnt)
                if total > 10000:
                    hot_ids.append(music.id)
        self.guess_data = [m for m in self.music_list if m.id in hot_ids]
        logger.info(f"猜歌数据：{len(self.guess_data)} 首热门歌曲")

    def find_music_by_keyword(self, keyword: str) -> MusicList:
        """按关键词搜索歌曲（标题、别名）。"""
        result = MusicList()
        keyword_lower = keyword.lower()

        # 先按标题搜索
        for m in self.music_list:
            if keyword_lower in m.title.lower():
                result.append(m)

        # 再按别名搜索
        for a in self.alias_list:
            if keyword_lower in [al.lower() for al in a.Alias]:
                music = self.music_list.by_id(a.SongID)
                if music and music not in result:
                    result.append(music)

        return result

    def find_music_by_alias(self, alias_name: str) -> MusicList:
        """按别名精确匹配歌曲。"""
        result = MusicList()
        alias_lower = alias_name.lower()
        for a in self.alias_list:
            if alias_lower in [al.lower() for al in a.Alias]:
                music = self.music_list.by_id(a.SongID)
                if music:
                    result.append(music)
        return result

    def get_aliases_for_music(self, music_id: int | str) -> list[str]:
        """获取歌曲的所有别名。"""
        for a in self.alias_list.by_id(music_id):
            return a.Alias
        return []

    def random_music(
        self,
        *,
        level: str | None = None,
        diff: int | None = None,
        type: str | None = None,
    ) -> Music | None:
        """随机选歌。"""
        candidates = list(self.music_list)
        if level:
            candidates = [m for m in candidates if level in m.level]
        if diff is not None:
            candidates = [m for m in candidates if diff < len(m.level)]
        if type:
            candidates = [m for m in candidates if m.type == type]
        return secure_choice(candidates) if candidates else None

    @staticmethod
    def compute_ra(ds: float, achievements: float) -> int:
        """计算单曲 Rating (Ra)。"""
        if achievements >= 100.5:
            base = ds + 2.0
        elif achievements >= 100.4999:
            base = ds + 1.5
        elif achievements >= 100.0:
            base = ds + 1.5
        elif achievements >= 99.5:
            base = ds + 1.0
        elif achievements >= 99.0:
            base = ds + 0.5
        elif achievements >= 98.0:
            base = ds
        elif achievements >= 97.0:
            base = ds - 0.5
        elif achievements >= 94.0:
            base = ds - 1.0
        elif achievements >= 90.0:
            base = ds - 2.0
        elif achievements >= 80.0:
            base = ds - 3.0
        elif achievements >= 75.0:
            base = ds - 4.0
        elif achievements >= 70.0:
            base = ds - 5.0
        elif achievements >= 60.0:
            base = ds - 6.0
        elif achievements >= 50.0:
            base = ds - 7.0
        else:
            base = 0.0
        return max(int(base), 0)


def secure_choice(items: list) -> Any:
    return items[secrets.randbelow(len(items))]
