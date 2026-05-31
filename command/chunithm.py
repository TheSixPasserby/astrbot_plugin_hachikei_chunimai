"""CHUNITHM 命令：B30、歌曲查询、Rating 计算。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error
from ..chunithm_data import (
    ChuDataManager, chu_rank_label, chu_rating,
    CHU_DIFF_LABELS, CHU_FC_LABELS, CHU_CHAIN_LABELS, CHU_CLEAR_LABELS,
)

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..lxns_client import LxnsAPI


def _get_friend_code(lxns: LxnsAPI, qq: int | None, username: str | None) -> int | None:
    """从 QQ 号或用户名获取好友码。此处返回 None，由调用方处理。"""
    return None


async def chu_b30_handler(
    event: AstrMessageEvent,
    lxns: LxnsAPI,
    data_mgr: ChuDataManager,
    **_: Any,
):
    """CHUNITHM B30 查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        query = args[1].strip() if len(args) > 1 else None

        # 从 @提及 获取 QQ
        qq = None
        try:
            from astrbot.api.message_components import At
            for comp in event.get_messages():
                if isinstance(comp, At):
                    qq = int(comp.qq)
        except Exception:
            pass

        # 获取玩家信息
        player = None
        friend_code = None
        if qq:
            player = await lxns.chu_player_by_qq(qq)
            friend_code = player.get("friend_code")
        elif query and query.isdigit():
            friend_code = int(query)
            player = await lxns.chu_player_by_fc(friend_code)

        if not player or not friend_code:
            yield event.plain_result("未找到玩家。请在落雪查分器绑定 QQ 号，或使用 `chub30 <好友码>` 查询。")
            return

        # 获取 B30
        bests_data = await lxns.chu_bests(friend_code)
        bests = bests_data.get("bests", [])
        selections = bests_data.get("selections", [])
        new_bests = bests_data.get("new_bests", [])

        name = player.get("name", "未知")
        rating = player.get("rating", 0)

        lines = [f"🎵 {name} 的 CHUNITHM Rating 构成"]
        lines.append(f"总 Rating: {rating}")
        lines.append("")

        # Best 30
        if bests:
            lines.append("═══ Best 30 ═══")
            total = 0
            for i, s in enumerate(bests[:30], 1):
                r = s.get("rating", 0)
                total += r
                fc = CHU_FC_LABELS.get(s.get("full_combo", ""), "")
                rank = chu_rank_label(s.get("score", 0))
                lines.append(
                    f"{i:2d}. {s.get('song_name', '?')} [{s.get('level', '?')}] "
                    f"| {s.get('score', 0)} | {rank} | R:{r:.1f} {fc}"
                )
            lines.append(f"Best 30 均值: {total / min(30, len(bests)):.2f}")

        # Selection 10
        if selections:
            lines.append("")
            lines.append("═══ Selection 10 ═══")
            total = 0
            for i, s in enumerate(selections[:10], 1):
                r = s.get("rating", 0)
                total += r
                lines.append(
                    f"{i:2d}. {s.get('song_name', '?')} [{s.get('level', '?')}] "
                    f"| {s.get('score', 0)} | R:{r:.1f}"
                )
            lines.append(f"Selection 10 均值: {total / min(10, len(selections)):.2f}")

        # New Best 20
        if new_bests:
            lines.append("")
            lines.append("═══ New Best 20 ═══")
            total = 0
            for i, s in enumerate(new_bests[:20], 1):
                r = s.get("rating", 0)
                total += r
                lines.append(
                    f"{i:2d}. {s.get('song_name', '?')} [{s.get('level', '?')}] "
                    f"| {s.get('score', 0)} | R:{r:.1f}"
                )
            lines.append(f"New Best 20 均值: {total / min(20, len(new_bests)):.2f}")

        yield event.make_result().use_markdown(True).message("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("CHUNITHM B30 查询异常")
        yield event.plain_result(f"查询失败：{e}")


async def chu_minfo_handler(
    event: AstrMessageEvent,
    lxns: LxnsAPI,
    data_mgr: ChuDataManager,
    **_: Any,
):
    """CHUNITHM 单曲成绩查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：chuminfo <歌曲名/ID>")
            return

        query = args[1].strip()

        # 获取玩家 QQ
        qq = None
        try:
            from astrbot.api.message_components import At
            for comp in event.get_messages():
                if isinstance(comp, At):
                    qq = int(comp.qq)
        except Exception:
            pass

        if not qq:
            yield event.plain_result("请 @ 一位已绑定落雪查分器的用户。")
            return

        player = await lxns.chu_player_by_qq(qq)
        fc = player.get("friend_code")
        if not fc:
            yield event.plain_result("未找到该玩家。")
            return

        # 查找歌曲
        song = data_mgr.find_by_id(query)
        if not song:
            results = data_mgr.find_by_keyword(query)
            if results:
                song = results[0]
            else:
                yield event.plain_result("未找到匹配的歌曲。")
                return

        # 获取成绩
        score = await lxns.chu_best(fc, song_id=song.id)

        fc_label = CHU_FC_LABELS.get(score.get("full_combo", ""), "-")
        chain_label = CHU_CHAIN_LABELS.get(score.get("full_chain", ""), "-")
        clear_label = CHU_CLEAR_LABELS.get(score.get("clear", ""), "-")
        rank = chu_rank_label(score.get("score", 0))

        lines = [
            f"🎵 {song.title} (ID:{song.id})",
            f"  分数: {score.get('score', 0)} | 评级: {rank}",
            f"  CLEAR: {clear_label} | FC: {fc_label} | Chain: {chain_label}",
            f"  Rating: {score.get('rating', 0):.1f}",
        ]
        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("CHUNITHM minfo 异常")
        yield event.plain_result(f"查询失败：{e}")


async def chu_search_handler(
    event: AstrMessageEvent,
    data_mgr: ChuDataManager,
    **_: Any,
):
    """CHUNITHM 歌曲搜索。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：chusearch <关键词>")
            return

        keyword = args[1].strip()
        results = data_mgr.find_by_keyword(keyword)

        if not results:
            yield event.plain_result(f"未找到包含「{keyword}」的歌曲。")
            return

        if len(results) == 1:
            song = results[0]
            levels = " / ".join(
                f"{d.get('level', '?')}" for d in song.difficulties
            )
            yield event.plain_result(
                f"🎵 {song.title} (ID:{song.id})\n"
                f"  曲师: {song.artist}\n"
                f"  分类: {song.genre} | BPM: {song.bpm}\n"
                f"  难度: {levels}"
            )
            return

        lines = [f"找到 {len(results)} 首歌曲："]
        for s in results[:20]:
            lines.append(f"  {s.id}. {s.title} [{s.artist}]")
        if len(results) > 20:
            lines.append(f"  ...还有 {len(results) - 20} 首")
        yield event.plain_result("\n".join(lines))

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def chu_id_handler(
    event: AstrMessageEvent,
    data_mgr: ChuDataManager,
    **_: Any,
):
    """CHUNITHM 按 ID 查询。"""
    try:
        args = event.get_message_str().strip().split()
        if len(args) < 2:
            yield event.plain_result("用法：chuid <编号>")
            return

        song = data_mgr.find_by_id(args[1])
        if not song:
            yield event.plain_result(f"未找到 ID 为 {args[1]} 的歌曲。")
            return

        levels = " / ".join(f"{d.get('level', '?')}" for d in song.difficulties)
        yield event.plain_result(
            f"🎵 {song.title} (ID:{song.id})\n"
            f"  曲师: {song.artist}\n"
            f"  分类: {song.genre} | BPM: {song.bpm}\n"
            f"  难度: {levels}"
        )

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")
