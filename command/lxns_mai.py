"""落雪查分器 - maimai DX 命令：B50、歌曲查询。"""

from __future__ import annotations

import asyncio

from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error
from ..music_data import MusicDataManager


def _fmt_fc(fs: str | None) -> str:
    """格式化 FC/FS 标签：fcp -> FC+, app -> AP+, fsdp -> FDX+ 等。"""
    if not fs:
        return "-"
    mapping = {
        "app": "AP+", "ap": "AP", "fcp": "FC+", "fc": "FC",
        "fsdp": "FDX+", "fsd": "FDX", "fsp": "FS+", "fs": "FS", "sync": "SYNC",
    }
    return mapping.get(fs.lower(), fs.upper())


def _fmt_rate(rate: str | None) -> str:
    """格式化评级标签：sssp -> SSS+, sss -> SSS 等。"""
    if not rate:
        return "-"
    mapping = {
        "sssp": "SSS+", "sss": "SSS", "ssp": "SS+", "ss": "SS",
        "sp": "S+", "s": "S", "aaa": "AAA", "aa": "AA", "a": "A",
        "bbb": "BBB", "bb": "BB", "b": "B", "c": "C", "d": "D",
    }
    return mapping.get(rate.lower(), rate.upper())

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..lxns_client import LxnsAPI


async def lxns_mai_b50_handler(
    event: AstrMessageEvent,
    lxns: LxnsAPI,
    qq: int | None = None,
    music_data: MusicDataManager | None = None,
    **_: Any,
):
    """落雪 maimai DX B50 查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        query = args[1].strip() if len(args) > 1 else None

        # 构建歌曲定数查找表：{(song_id, difficulty): level_value}
        ds_map: dict[tuple[int, int], float] = {}
        # 1. 从落雪 API 获取（权威数据源）
        try:
            song_data = await asyncio.wait_for(lxns.mai_song_list(), timeout=10)
            for s in song_data.get("songs", []):
                sid = int(s["id"])
                for diff in s.get("difficulties", {}).get("standard", []):
                    ds_map[(sid, diff["difficulty"])] = diff["level_value"]
                for diff in s.get("difficulties", {}).get("dx", []):
                    ds_map[(sid, diff["difficulty"])] = diff["level_value"]
            logger.info(f"落雪歌曲定数加载: {len(ds_map)} 条")
        except asyncio.TimeoutError:
            logger.warning("落雪歌曲数据加载超时")
            yield event.plain_result("⚠️ 落雪歌曲数据加载超时，将使用本地数据。")
        except Exception as e:
            logger.warning(f"落雪歌曲数据加载失败: {e}")
            yield event.plain_result("⚠️ 从落雪获取定数信息失败，将使用本地数据。")
        # 2. 从本地 DivingFish 数据补充（ID 映射：水鱼5位=落雪4位+10000）
        if music_data:
            for m in music_data.music_list:
                mid = int(m.id)
                lxns_id = mid - 10000 if mid > 9999 else mid
                for i, d in enumerate(m.ds):
                    ds_map.setdefault((lxns_id, i), d)

        def _get_ds(song_id: int, level_index: int) -> str:
            lv = ds_map.get((song_id, level_index))
            return f"{lv:.1f}" if lv is not None else "?"

        # 获取玩家信息：优先个人 API
        player = None
        friend_code = None
        use_personal = False

        if lxns._user_token:
            try:
                player = await lxns.mai_user_player()
                friend_code = player.get("friend_code")
                use_personal = True
            except Exception:
                pass

        if not player and qq and lxns._dev_key:
            try:
                player = await asyncio.wait_for(lxns.mai_player_by_qq(qq), timeout=10)
                friend_code = player.get("friend_code")
            except Exception:
                pass
        if not player and query and query.isdigit():
            friend_code = int(query)
            player = await lxns.mai_player_by_fc(friend_code)

        if not player or not friend_code:
            yield event.plain_result(
                "未找到玩家。请先执行 `bindqq <QQ号>` 绑定，或使用 `maib50 <好友码>` 查询。"
            )
            return

        # 获取 B50
        if use_personal:
            bests_data = await lxns._user_get("/user/maimai/player/bests")
        else:
            bests_data = await lxns.mai_bests(friend_code)

        name = player.get("name", "未知")
        rating = player.get("rating", 0)
        standard_total = bests_data.get("standard_total", 0)
        dx_total = bests_data.get("dx_total", 0)
        standard = bests_data.get("standard", [])
        dx = bests_data.get("dx", [])

        lines = [f"# 🎵 {name} 的 Best 50\n"]
        lines.append(f"**Rating: {rating}** (旧谱面: {standard_total} / 新谱面: {dx_total})\n")

        _DIFF_LABELS = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"]

        def _fmt_song(s: dict) -> str:
            stype = "DX" if s.get("type") == "dx" else "ST"
            diff = _DIFF_LABELS[s.get("level_index", 3)] if s.get("level_index", 3) < 5 else "?"
            return f"【{stype}】{s.get('song_name', '?')} [{diff}]"

        def _render_table(title: str, items: list, limit: int) -> None:
            if not items:
                return
            lines.append(f"## {title}\n")
            lines.append("| # | 曲名 | 定数 | 达成率 | DX分 | 评级 | Rating | FC |")
            lines.append("|---|------|------|--------|------|------|--------|-----|")
            for i, s in enumerate(items[:limit], 1):
                fc = _fmt_fc(s.get("fc"))
                rate = _fmt_rate(s.get("rate"))
                ds = _get_ds(s.get("id", 0), s.get("level_index", 0))
                r = s.get("dx_rating", 0) or s.get("rating", 0)
                lines.append(
                    f"| {i} | {_fmt_song(s)} | {ds} "
                    f"| {s.get('achievements', 0):.4f}% | {s.get('dx_score', 0)} | {rate} | {r:.1f} | {fc} |"
                )
            lines.append("")

        _render_table("旧版本 Best 35", standard, 35)
        _render_table("新版本 Best 15", dx, 15)

        # 查分器状态（与分表隔开，后续分表改为图片时此行保持文本）
        lines.append("")
        lines.append("——————————————")
        lines.append("由落雪咖啡屋提供数据")
        lines.append("发送「更改查分器 水鱼/落雪」以切换")

        yield event.make_result().use_markdown(True).message("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("落雪 maimai B50 查询异常")
        yield event.plain_result(f"查询失败：{e}")


async def lxns_mai_minfo_handler(
    event: AstrMessageEvent,
    lxns: LxnsAPI,
    qq: int | None = None,
    **_: Any,
):
    """落雪 maimai DX 单曲成绩查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：maiminfo <歌曲名/ID>")
            return

        query = args[1].strip()

        # 获取玩家信息
        fc = None
        use_personal = False
        if lxns._user_token:
            try:
                player = await lxns.mai_user_player()
                fc = player.get("friend_code")
                use_personal = True
            except Exception:
                pass
        if not fc and qq:
            player = await lxns.mai_player_by_qq(qq)
            fc = player.get("friend_code")
        if not fc:
            yield event.plain_result("未找到玩家。请先执行 `bindqq <QQ号>` 绑定。")
            return

        # 获取单曲成绩
        params = {}
        if query.isdigit():
            params["song_id"] = int(query)
        else:
            params["song_name"] = query

        if use_personal:
            score = await lxns._user_get("/user/maimai/player/best", params=params)
        else:
            score = await lxns.mai_best(fc, **params)

        fc_label = score.get("fc", "") or "-"
        fs_label = score.get("fs", "") or "-"
        rate = score.get("rate", "")
        lines = [
            f"🎵 {score.get('song_name', query)} (ID:{score.get('id', '?')})",
            f"  [{score.get('level', '?')}] {score.get('type', '?')}",
            f"  达成率: {score.get('achievements', 0):.4f}% | 评级: {rate}",
            f"  DX分数: {score.get('dx_score', 0)} | FC: {fc_label} | FS: {fs_label}",
        ]
        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("落雪 maimai minfo 异常")
        yield event.plain_result(f"查询失败：{e}")
