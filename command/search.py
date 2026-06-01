"""搜索命令：查歌、定数查歌、BPM查歌、曲师查歌、谱师查歌、别名查歌、ID查询。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error
from ..music_data import MusicDataManager, DIFF_INDEX_TO_LABEL

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


def _format_music_info(music) -> str:
    """格式化歌曲信息为文本。"""
    levels = " / ".join(f"{l}" for l in music.level)
    ds_list = " / ".join(f"{d:.1f}" for d in music.ds)
    return (
        f"🎵 {music.title} (ID:{music.id})\n"
        f"  类型: {music.type} | 分类: {music.basic_info.genre}\n"
        f"  曲师: {music.basic_info.artist}\n"
        f"  BPM: {music.basic_info.bpm} | 版本: {music.basic_info.version}\n"
        f"  难度: {levels}\n"
        f"  定数: {ds_list}"
    )


async def search_music_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """查歌。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：查歌 <关键词>")
            return

        keyword = args[1].strip()
        results = data_mgr.find_music_by_keyword(keyword)

        if not results:
            yield event.plain_result(f"未找到包含「{keyword}」的歌曲。")
            return

        if len(results) == 1:
            yield event.plain_result(_format_music_info(results[0]))
            return

        lines = [f"找到 {len(results)} 首歌曲："]
        for m in results[:20]:
            lines.append(f"  {m.id}. {m.title} [{m.type}]")
        if len(results) > 20:
            lines.append(f"  ...还有 {len(results) - 20} 首")
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        logger.exception("查歌异常")
        yield event.plain_result(f"查询失败：{e}")


async def search_base_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """定数查歌。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：定数查歌 <定数或范围，如 12.0 或 11.5-12.0>")
            return

        query = args[1].strip()
        m = re.match(r"^([\d.]+)(?:\s*[-~]\s*([\d.]+))?$", query)
        if not m:
            yield event.plain_result("格式错误，请输入如 12.0 或 11.5-12.0")
            return

        low = float(m.group(1))
        high = float(m.group(2)) if m.group(2) else low

        results = []
        for music in data_mgr.music_list:
            for i, ds in enumerate(music.ds):
                if low <= ds <= high:
                    label = DIFF_INDEX_TO_LABEL.get(i, str(i))
                    results.append((ds, f"{music.id}. [{label}] {music.title}"))

        results.sort(key=lambda x: x[0])
        if not results:
            yield event.plain_result(f"未找到定数在 {low}-{high} 范围内的谱面。")
            return

        lines = [f"定数 {low}~{high} 的谱面 ({len(results)} 个)："]
        for _, text in results[:30]:
            lines.append(f"  {text}")
        if len(results) > 30:
            lines.append(f"  ...还有 {len(results) - 30} 个")
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        logger.exception("定数查歌异常")
        yield event.plain_result(f"查询失败：{e}")


async def search_bpm_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """BPM 查歌。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：bpm查歌 <BPM或范围>")
            return

        query = args[1].strip()
        m = re.match(r"^([\d.]+)(?:\s*[-~]\s*([\d.]+))?$", query)
        if not m:
            yield event.plain_result("格式错误")
            return

        low = float(m.group(1))
        high = float(m.group(2)) if m.group(2) else low

        results = [
            music for music in data_mgr.music_list
            if low <= music.basic_info.bpm <= high
        ]

        if not results:
            yield event.plain_result(f"未找到 BPM 在 {low}-{high} 范围内的歌曲。")
            return

        lines = [f"BPM {low}~{high} 的歌曲 ({len(results)} 首)："]
        for m in results[:30]:
            lines.append(f"  {m.id}. {m.title} [BPM:{m.basic_info.bpm}]")
        if len(results) > 30:
            lines.append(f"  ...还有 {len(results) - 30} 首")
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        logger.exception("BPM查歌异常")
        yield event.plain_result(f"查询失败：{e}")


async def search_artist_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """曲师查歌。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：曲师查歌 <艺术家名>")
            return

        keyword = args[1].strip().lower()
        results = [m for m in data_mgr.music_list if keyword in m.basic_info.artist.lower()]

        if not results:
            yield event.plain_result(f"未找到曲师包含「{keyword}」的歌曲。")
            return

        lines = [f"曲师包含「{keyword}」的歌曲 ({len(results)} 首)："]
        for m in results[:30]:
            lines.append(f"  {m.id}. {m.title} — {m.basic_info.artist}")
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def search_charter_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """谱师查歌。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：谱师查歌 <谱师名>")
            return

        keyword = args[1].strip().lower()
        results = []
        for music in data_mgr.music_list:
            for i, chart in enumerate(music.charts):
                if keyword in chart.charter.lower():
                    label = DIFF_INDEX_TO_LABEL.get(i, str(i))
                    results.append(f"{music.id}. [{label}] {music.title} — {chart.charter}")

        if not results:
            yield event.plain_result(f"未找到谱师包含「{keyword}」的谱面。")
            return

        lines = [f"谱师包含「{keyword}」的谱面 ({len(results)} 个)："]
        lines.extend(f"  {r}" for r in results[:30])
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def search_alias_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """别名查歌：xxx是什么歌。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(.+?)(是什么歌|是啥歌)$", text)
        if not m:
            return

        alias_name = m.group(1).strip()
        results = data_mgr.find_music_by_alias(alias_name)

        if not results:
            # 尝试模糊搜索
            results = data_mgr.find_music_by_keyword(alias_name)

        if not results:
            yield event.plain_result(f"未找到「{alias_name}」对应的歌曲。")
            return

        if len(results) == 1:
            yield event.plain_result(_format_music_info(results[0]))
            return

        lines = [f"找到 {len(results)} 首匹配歌曲："]
        for music in results[:10]:
            lines.append(f"  {music.id}. {music.title}")
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def query_by_id_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """按 ID 查询歌曲。"""
    try:
        args = event.get_message_str().strip().split()
        if len(args) < 2:
            yield event.plain_result("用法：id <编号>")
            return

        music_id = args[1].strip()
        music = data_mgr.music_list.by_id(music_id)
        if not music:
            yield event.plain_result(f"未找到 ID 为 {music_id} 的歌曲。")
            return

        yield event.plain_result(_format_music_info(music))

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")
