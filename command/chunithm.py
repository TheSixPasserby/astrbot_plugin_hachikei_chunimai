"""CHUNITHM 命令：B30、歌曲查询、Rating 计算。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error
from ..chu_data import ChuDataManager, chu_rank_label, CHU_FC_LABELS, CHU_CHAIN_LABELS
from ..utils import fmt_rate as _fmt_rate

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..lxns_client import LxnsAPI


async def chu_b30_handler(
    event: AstrMessageEvent,
    lxns: LxnsAPI,
    data_mgr: ChuDataManager,
    qq: int | None = None,
    **_: Any,
):
    """CHUNITHM B30 查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        query = args[1].strip() if len(args) > 1 else None

        # 构建歌曲定数查找表
        ds_map: dict[tuple[int, int], float] = {}
        try:
            song_data = await lxns.chu_song_list()
            for s in song_data.get("songs", []):
                sid = int(s["id"])
                for diff in s.get("difficulties", []):
                    ds_map[(sid, diff["difficulty"])] = diff["level_value"]
        except Exception as e:
            logger.warning(f"CHUNITHM 歌曲数据加载失败: {e}")
            yield event.plain_result("⚠️ 从落雪获取定数信息失败，将使用本地数据（部分歌曲定数可能缺失）。")

        def _get_ds(song_id: int, level_index: int) -> str:
            lv = ds_map.get((song_id, level_index))
            return f"{lv:.1f}" if lv is not None else "?"

        # 从 @提及 获取 QQ（如果外部未传入）
        if qq is None:
            try:
                from astrbot.api.message_components import At
                for comp in event.get_messages():
                    if isinstance(comp, At):
                        qq = int(comp.qq)
            except Exception:
                pass

        # 获取玩家信息：优先个人 API，其次开发者 API
        player = None
        friend_code = None
        use_personal = False

        if lxns._user_token:
            # 有个人密钥，直接用个人 API
            try:
                player = await lxns.chu_user_player()
                friend_code = player.get("friend_code")
                use_personal = True
            except Exception:
                pass

        if not player and qq:
            player = await lxns.chu_player_by_qq(qq)
            friend_code = player.get("friend_code")
        elif not player and query and query.isdigit():
            friend_code = int(query)
            player = await lxns.chu_player_by_fc(friend_code)

        if not player or not friend_code:
            yield event.plain_result(
                "未找到玩家。请先执行 `bindqq <QQ号>` 绑定，或使用 `chub30 <好友码>` 查询。"
            )
            return

        # 获取 B30：优先个人 API
        if use_personal:
            bests_data = await lxns._user_get("/user/chunithm/player/bests")
        else:
            bests_data = await lxns.chu_bests(friend_code)
        bests = bests_data.get("bests", [])
        selections = bests_data.get("selections", [])
        new_bests = bests_data.get("new_bests", [])

        name = player.get("name", "未知")
        rating = player.get("rating", 0)

        lines = [f"🎵 {name} 的 CHUNITHM Rating 构成"]
        lines.append(f"总 Rating: {rating}")
        lines.append("")

        _CHU_DIFF = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA", "WORLD'S END"]

        def _fmt_song(s: dict) -> str:
            diff = _CHU_DIFF[s.get("level_index", 3)] if s.get("level_index", 3) < 6 else "?"
            return f"{s.get('song_name', '?')} [{diff}]"

        def _render_table(title: str, items: list, limit: int) -> None:
            if not items:
                return
            lines.append(f"## {title}\n")
            lines.append("| # | 曲名 | 定数 | 分数 | 评级 | Rating | FC |")
            lines.append("|---|------|------|------|------|--------|-----|")
            total = 0.0
            for i, s in enumerate(items[:limit], 1):
                r = s.get("rating", 0)
                total += r
                fc = CHU_FC_LABELS.get(s.get("full_combo", ""), "-").upper()
                rank = _fmt_rate(s.get("rank"))
                ds = _get_ds(s.get("id", 0), s.get("level_index", 3))
                lines.append(
                    f"| {i} | {_fmt_song(s)} | {ds} "
                    f"| {s.get('score', 0)} | {rank} | {r:.2f} | {fc} |"
                )
            lines.append(f"\n**{title} 均值: {total / min(limit, len(items)):.2f}**\n")

        _render_table("Best 30", bests, 30)
        _render_table("Selection 10", selections, 10)
        _render_table("New Best 20", new_bests, 20)

        # 查分器状态
        lines.append("")
        lines.append("——————————————")
        lines.append("由落雪咖啡屋提供数据")

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
    qq: int | None = None,
    **_: Any,
):
    """CHUNITHM 单曲成绩查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：chuminfo <歌曲名/ID>")
            return

        query = args[1].strip()

        # 从 @提及 获取 QQ（如果外部未传入）
        if qq is None:
            try:
                from astrbot.api.message_components import At
                for comp in event.get_messages():
                    if isinstance(comp, At):
                        qq = int(comp.qq)
            except Exception:
                pass

        # 获取玩家信息：优先个人 API
        fc = None
        use_personal = False
        if lxns._user_token:
            try:
                player = await lxns.chu_user_player()
                fc = player.get("friend_code")
                use_personal = True
            except Exception:
                pass
        if not fc and qq:
            player = await lxns.chu_player_by_qq(qq)
            fc = player.get("friend_code")
        if not fc:
            yield event.plain_result("未找到玩家。请先执行 `bindqq <QQ号>` 绑定。")
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

        # 获取成绩：优先个人 API
        if use_personal:
            # 个人 API 无单曲查询端点，从全量成绩中筛选
            all_scores = await lxns.chu_user_scores()
            score = next((s for s in all_scores if s.get("id") == song.id), None)
            if not score:
                yield event.plain_result(f"未找到「{song.title}」的成绩记录。")
                return
        else:
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


async def chu_alias_query_handler(
    event: AstrMessageEvent,
    data_mgr: ChuDataManager,
    **_: Any,
):
    """查询 CHUNITHM 歌曲别名：X有什么别名。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(.+)\s有什么别[名称]$", text)
        if not m:
            return

        query = m.group(1).strip()
        song = data_mgr.find_by_id(query)
        if not song:
            results = data_mgr.find_by_keyword(query)
            if results:
                song = results[0]
            else:
                yield event.plain_result("未找到匹配的歌曲。")
                return

        aliases = data_mgr.get_aliases(song.id)
        if aliases:
            yield event.plain_result(
                f"🎵 {song.title} (ID:{song.id}) 的别名：\n" +
                "\n".join(f"  - {a}" for a in aliases)
            )
        else:
            yield event.plain_result(f"🎵 {song.title} 暂无别名。")

    except Exception as e:
        logger.exception("CHUNITHM 别名查询异常")
        yield event.plain_result(f"查询失败：{e}")
