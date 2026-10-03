"""趣味功能：今日运势、随机推荐、随机选歌。"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Any

from ..mai_data import MusicDataManager
from ..utils import qq_hash, now_cn, secure_choice

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

_FORTUNES = [
    ("大吉", "今天打 mai 一定会有好成绩！"),
    ("中吉", "稳扎稳打，今天适合刷分。"),
    ("小吉", "小心手滑，注意节奏。"),
    ("吉", "平平淡淡才是真。"),
    ("末吉", "今天可能不太顺利，休息一下吧。"),
]


async def daily_fortune_handler(event: AstrMessageEvent, data_mgr: MusicDataManager, **_: Any):
    """每日运势。"""
    qq = event.get_sender_id()
    today = now_cn().strftime("%Y%m%d")
    seed = int(f"{qq_hash(qq)}{today}")
    rng = random.Random(seed)

    music = (
        secure_choice(list(data_mgr.music_list))
        if data_mgr.music_list else None
    )
    fortune = rng.choice(_FORTUNES)

    lines = [f"🎱 今日运势 — {fortune[0]}", fortune[1]]
    if music:
        lines.append(f"🎵 今日推荐：{music.title}")

    yield event.plain_result("\n".join(lines))


async def mai_what_handler(event: AstrMessageEvent, data_mgr: MusicDataManager, **_: Any):
    """mai什么 — 随机推荐。"""
    music = (
        secure_choice(list(data_mgr.music_list))
        if data_mgr.music_list else None
    )
    if not music:
        yield event.plain_result("曲库为空。")
        return

    levels = " / ".join(music.level)
    yield event.plain_result(
        f"🎵 随机推荐：{music.title}\n"
        f"  曲师: {music.basic_info.artist}\n"
        f"  难度: {levels}\n"
        f"  BPM: {music.basic_info.bpm}"
    )


async def random_song_handler(event: AstrMessageEvent, data_mgr: MusicDataManager, **_: Any):
    """来/随/给个 + 难度等级。"""
    from ..mai_data import DIFF_LABEL_TO_INDEX

    text = event.get_message_str().strip()
    m = re.match(r"^[来随给]个(?:(dx|sd|标准))?([绿黄红紫白]?)([0-9]+\+?)$", text)
    if not m:
        return

    type_filter = m.group(1)
    diff_char = m.group(2)
    level = m.group(3)

    type_map = {"dx": "DX", "sd": "SD", "标准": "SD"}
    music_type = type_map.get(type_filter) if type_filter else None
    diff_idx = DIFF_LABEL_TO_INDEX.get(diff_char)

    music = data_mgr.random_music(level=level, diff=diff_idx, type=music_type)
    if not music:
        yield event.plain_result("未找到符合条件的歌曲。")
        return

    levels = " / ".join(music.level)
    yield event.plain_result(
        f"🎵 随机选歌：{music.title}\n"
        f"  类型: {music.type} | 难度: {levels}"
    )
