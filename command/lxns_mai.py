"""落雪查分器 - maimai DX 命令：B50、歌曲查询。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error


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
    **_: Any,
):
    """落雪 maimai DX B50 查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        query = args[1].strip() if len(args) > 1 else None

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

        if not player and qq:
            player = await lxns.mai_player_by_qq(qq)
            friend_code = player.get("friend_code")
        elif not player and query and query.isdigit():
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

        if standard:
            lines.append("## 旧版本 Best 35\n")
            lines.append("| # | 难度 | 曲名 | 达成率 | DX分 | 评级 | FC |")
            lines.append("|---|------|------|--------|------|------|-----|")
            for i, s in enumerate(standard[:35], 1):
                fc = _fmt_fc(s.get("fc"))
                rate = _fmt_rate(s.get("rate"))
                lines.append(
                    f"| {i} | {s.get('level', '?')} | {s.get('song_name', '?')} "
                    f"| {s.get('achievements', 0):.4f}% | {s.get('dx_score', 0)} | {rate} | {fc} |"
                )

        if dx:
            lines.append("\n## 新版本 Best 15\n")
            lines.append("| # | 难度 | 曲名 | 达成率 | DX分 | 评级 | FC |")
            lines.append("|---|------|------|--------|------|------|-----|")
            for i, s in enumerate(dx[:15], 1):
                fc = _fmt_fc(s.get("fc"))
                rate = _fmt_rate(s.get("rate"))
                lines.append(
                    f"| {i} | {s.get('level', '?')} | {s.get('song_name', '?')} "
                    f"| {s.get('achievements', 0):.4f}% | {s.get('dx_score', 0)} | {rate} | {fc} |"
                )

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
