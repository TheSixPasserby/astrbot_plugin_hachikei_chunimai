"""Pydantic 数据模型。复用自 astrbot_plugin_maimaidx。"""

from __future__ import annotations

from collections import namedtuple
from typing import Optional, Union

from pydantic import BaseModel, Field


# --- 歌曲相关 ---

class Stats(BaseModel):
    cnt: Optional[float] = None
    diff: Optional[str] = None
    fit_diff: Optional[float] = None
    avg: Optional[float] = None
    avg_dx: Optional[float] = None
    std_dev: Optional[float] = None
    dist: Optional[list[int]] = None
    fc_dist: Optional[list[float]] = None


Notes1 = namedtuple("Notes", ["tap", "hold", "slide", "brk"])
Notes2 = namedtuple("Notes", ["tap", "hold", "slide", "touch", "brk"])


class Chart(BaseModel):
    notes: Union[Notes1, Notes2]
    charter: str = ""


class BasicInfo(BaseModel):
    title: str
    artist: str
    genre: str
    bpm: int
    release_date: Optional[str] = ""
    version: str = Field(alias="from")
    is_new: bool


class Music(BaseModel):
    id: str
    title: str
    type: str
    ds: list[float]
    level: list[str]
    cids: list[int]
    charts: list[Chart]
    basic_info: BasicInfo
    stats: Optional[list[Optional[Stats]]] = []
    diff: Optional[list[int]] = []


# --- 成绩相关 ---

class PlayInfo(BaseModel):
    achievements: float
    fc: str = ""
    fs: str = ""
    level: str
    level_index: int
    title: str
    type: str
    ds: float = 0
    dxScore: int = 0
    ra: int = 0
    rate: str = ""


class ChartInfo(PlayInfo):
    level_label: str
    song_id: int


class Data(BaseModel):
    sd: Optional[list[ChartInfo]] = None
    dx: Optional[list[ChartInfo]] = None


class _UserInfo(BaseModel):
    additional_rating: Optional[int]
    nickname: Optional[str]
    plate: Optional[str] = None
    rating: Optional[int]
    username: Optional[str]


class UserInfo(_UserInfo):
    charts: Optional[Data]


class PlayInfoDefault(PlayInfo):
    song_id: int = Field(alias="id")
    table_level: list[int] = []


class PlayInfoDev(ChartInfo): ...


class UserInfoDev(_UserInfo):
    records: Optional[list[PlayInfoDev]] = None


# --- 牌桌相关 ---

class TableData(BaseModel):
    achievements: float
    fc: str = ""


class PlanInfo(BaseModel):
    completed: Union[PlayInfoDefault, PlayInfoDev] = None
    unfinished: Union[PlayInfoDefault, PlayInfoDev] = None


class RiseScore(BaseModel):
    song_id: int
    title: str
    type: str
    level_index: int
    ds: float
    ra: int
    rate: str
    achievements: float
    oldra: Optional[int] = 0
    oldrate: Optional[str] = "D"
    oldachievements: Optional[float] = 0


# --- 排行 ---

class UserRanking(BaseModel):
    username: str
    ra: int


# --- 别名相关 ---

class Alias(BaseModel):
    SongID: int
    Name: str
    Alias: list[str]


class StatusBase(BaseModel):
    SongID: int
    ApplyUID: int
    ApplyAlias: str


class Approved(StatusBase):
    Tag: str
    Name: str
    GroupID: Optional[int] = None
    WSUUID: Optional[str] = None


class AliasStatus(StatusBase):
    Tag: str
    Name: str
    Time: str
    AgreeVotes: Optional[int] = 0
    Votes: int


class Reviewed(StatusBase):
    Tag: str
    Name: str


class PushAliasStatus(BaseModel):
    Type: str
    Status: Union[AliasStatus, Approved, Reviewed]


# --- 猜歌 ---

class GuessData(BaseModel):
    music: Music
    img: str
    answer: list[str]
    end: bool = False


# --- API ---

class APIResult(BaseModel):
    code: int = 0
    content: Union[dict, list, str]


# --- 机厅 ---

class Arcade(BaseModel):
    name: str
    address: str = ""
    machine_count: int = 0
    aliases: list[str] = []


class ArcadeQueue(BaseModel):
    arcade_name: str
    person_count: int = 0
    card_count: int = 0
    updated_by: str = ""
    updated_at: float = 0.0
