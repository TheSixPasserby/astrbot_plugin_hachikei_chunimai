"""查分命令：B50、minfo、ginfo、分数线、分数计算、排名。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, MusicNotPlayError, describe_error
from ..models import UserInfo
from ..mai_data import MusicDataManager, achievements_label, DIFF_INDEX_TO_LABEL
from ..utils import fmt_fc as _fmt_fc, fmt_rate as _fmt_rate
from ..image_utils import pie_chart, image_to_base64

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..api_client import MaimaiAPI
    from ..lxns_client import LxnsAPI


def _extract_qq_from_at(event: AstrMessageEvent) -> int | None:
    """从 @提及 中提取 QQ 号。"""
    try:
        from astrbot.api.message_components import At
        for comp in event.get_messages():
            if isinstance(comp, At):
                return int(comp.qq)
    except Exception:
        pass
    return None


async def mai_b50_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    qq: int | None = None,
    **_: Any,
):
    """生成 Best 50 图片。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        username = args[1].strip() if len(args) > 1 else None
        if qq is None:
            qq = _extract_qq_from_at(event)

        user_info = await api.query_user_b50(qqid=qq, username=username)

        if not user_info.charts:
            yield event.plain_result("未找到游玩记录。")
            return

        # 构建 B50 markdown
        name = user_info.nickname or user_info.username or "未知"
        lines = [f"# 🎵 {name} 的 Best 50\n"]
        lines.append(f"**Rating: {user_info.rating}**\n")

        _DIFF_LABELS = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"]

        def _fmt_song(c) -> str:
            diff = _DIFF_LABELS[c.level_index] if c.level_index < 5 else "?"
            return f"【DX】{c.title} [{diff}]"

        def _render_table(title: str, items: list, limit: int) -> None:
            if not items:
                return
            total = sum(c.ra for c in items)
            lines.append(f"## {title} (总Ra: {total})\n")
            lines.append("| # | 曲名 | 定数 | 达成率 | 评级 | Ra | FC |")
            lines.append("|---|------|------|--------|------|-----|-----|")
            for i, c in enumerate(items[:limit], 1):
                fc = _fmt_fc(c.fc)
                rate = _fmt_rate(c.rate)
                ds = f"{c.ds:.1f}" if c.ds else "?"
                lines.append(
                    f"| {i} | {_fmt_song(c)} | {ds} | {c.achievements:.4f}% | {rate} | {c.ra} | {fc} |"
                )
            lines.append("")

        _render_table("SD Best 35", user_info.charts.sd or [], 35)
        _render_table("DX Best 15", user_info.charts.dx or [], 15)

        # 查分器状态
        lines.append("")
        lines.append("——————————————")
        lines.append("由水鱼查分器提供数据")
        lines.append("发送「更改查分器 水鱼/落雪」以切换")

        # TODO: 生成图片版本（需要 image_gen.py 完善后）
        yield event.make_result().use_markdown(True).message("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("B50 查询异常")
        yield event.plain_result(f"查询失败：{e}")


async def mai_minfo_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    qq: int | None = None,
    **_: Any,
):
    """查询个人歌曲成绩。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：minfo <歌曲名/ID/别名>")
            return

        query = args[1].strip()
        music = data_mgr.music_list.by_id(query)
        if not music:
            results = data_mgr.find_music_by_keyword(query)
            if len(results) == 1:
                music = results[0]
            elif len(results) > 1:
                names = "\n".join(f"  {m.id}. {m.title}" for m in results[:10])
                yield event.plain_result(f"找到多首歌曲，请指定 ID：\n{names}")
                return
        if not music:
            results = data_mgr.find_music_by_alias(query)
            if results:
                music = results[0]
        if not music:
            yield event.plain_result("未找到匹配的歌曲。")
            return

        if qq is None:
            qq = _extract_qq_from_at(event)
        try:
            records = await api.query_user_record_dev(qqid=qq, music_id=int(music.id))
        except MusicNotPlayError:
            yield event.plain_result(f"未查询到 {music.title} 的游玩记录。")
            return

        lines = [f"🎵 {music.title} (ID:{music.id})"]
        for r in records:
            label = DIFF_INDEX_TO_LABEL.get(r.level_index, "?")
            fc = r.fc.upper() if r.fc else "-"
            fs = r.fs.upper() if r.fs else "-"
            lines.append(
                f"  [{label}] {r.achievements:.4f}% | DX:{r.dxScore} | "
                f"Ra:{r.ra} | FC:{fc} FS:{fs}"
            )

        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("minfo 查询异常")
        yield event.plain_result(f"查询失败：{e}")


async def mai_ginfo_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    qq: int | None = None,
    **_: Any,
):
    """全球歌曲统计（用 Pillow 饼图替代 pyecharts + Playwright）。"""
    try:
        args = event.get_message_str().strip().split()
        if len(args) < 2:
            yield event.plain_result("用法：ginfo <歌曲名/ID> [难度]")
            return

        query = args[1]
        diff_idx = None
        if len(args) >= 3:
            diff_input = args[2].strip()
            diff_map = {"绿": 0, "黄": 1, "红": 2, "紫": 3, "白": 4,
                        "basic": 0, "advanced": 1, "expert": 2, "master": 3, "remaster": 4}
            diff_idx = diff_map.get(diff_input.lower())
            if diff_idx is None:
                try:
                    diff_idx = int(diff_input)
                except ValueError:
                    diff_idx = 3  # 默认 Master
        else:
            diff_idx = 3

        music = data_mgr.music_list.by_id(query)
        if not music:
            results = data_mgr.find_music_by_keyword(query)
            if results:
                music = results[0]
        if not music:
            results = data_mgr.find_music_by_alias(query)
            if results:
                music = results[0]
        if not music:
            yield event.plain_result("未找到匹配的歌曲。")
            return

        if diff_idx >= len(music.level):
            yield event.plain_result(f"该歌曲没有 {DIFF_INDEX_TO_LABEL.get(diff_idx, str(diff_idx))} 难度。")
            return

        stats = music.stats[diff_idx] if music.stats and diff_idx < len(music.stats) else None
        if not stats:
            yield event.plain_result("暂无该难度的统计数据。")
            return

        label = DIFF_INDEX_TO_LABEL.get(diff_idx, str(diff_idx))
        lines = [
            f"📊 {music.title} [{label}] 全球统计",
            f"游玩次数: {stats.cnt:.0f}" if stats.cnt else "游玩次数: N/A",
            f"拟合难度: {stats.fit_diff}" if stats.fit_diff else "",
            f"平均达成率: {stats.avg:.2f}%" if stats.avg else "",
            f"平均 DX 分: {stats.avg_dx:.2f}" if stats.avg_dx else "",
            f"标准差: {stats.std_dev:.2f}" if stats.std_dev else "",
        ]

        # Pillow 饼图
        if stats.dist:
            dist_labels = ["D", "C", "B", "BB", "BBB", "A", "AA", "AAA", "S", "S+", "SS", "SS+", "SSS", "SSS+"]
            dist_data = {}
            for i, v in enumerate(stats.dist):
                if i < len(dist_labels) and v > 0:
                    dist_data[dist_labels[i]] = v
            if dist_data:
                chart = pie_chart(dist_data, title=f"{music.title} [{label}] 分布")
                b64 = image_to_base64(chart)
                lines.append("")
                lines.append("（成绩分布饼图已生成）")

        text = "\n".join(l for l in lines if l)
        yield event.plain_result(text)

        # 如果有饼图，单独发送图片
        if stats.dist:
            from astrbot.api.message_components import Image as CompImage
            yield event.make_result().base64_image(b64)

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("ginfo 查询异常")
        yield event.plain_result(f"查询失败：{e}")


async def mai_score_line_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """分数线计算。"""
    try:
        text = event.get_message_str().strip()
        # 解析：分数线 <目标%> <歌曲名> [难度]
        m = re.match(r"^分数线\s+([\d.]+)%?\s+(.+?)(?:\s+(绿|黄|红|紫|白|basic|advanced|expert|master|remaster))?$", text, re.I)
        if not m:
            if "帮助" in text:
                yield event.plain_result(
                    "分数线用法：分数线 <目标%> <歌曲名> [难度]\n"
                    "例如：分数线 100.5% 幻影鬼andestly 紫"
                )
                return
            yield event.plain_result("用法：分数线 <目标%> <歌曲名> [难度]")
            return

        target = float(m.group(1))
        query = m.group(2).strip()
        diff_input = m.group(3)

        diff_idx = 3  # 默认 Master
        if diff_input:
            diff_map = {"绿": 0, "黄": 1, "红": 2, "紫": 3, "白": 4,
                        "basic": 0, "advanced": 1, "expert": 2, "master": 3, "remaster": 4}
            diff_idx = diff_map.get(diff_input.lower(), 3)

        music = data_mgr.music_list.by_id(query)
        if not music:
            results = data_mgr.find_music_by_keyword(query)
            if results:
                music = results[0]
        if not music:
            results = data_mgr.find_music_by_alias(query)
            if results:
                music = results[0]
        if not music:
            yield event.plain_result("未找到匹配的歌曲。")
            return

        if diff_idx >= len(music.charts):
            yield event.plain_result("该歌曲没有此难度。")
            return

        chart = music.charts[diff_idx]
        notes = chart.notes
        total_notes = notes.tap + notes.hold + notes.slide + notes.brk
        if hasattr(notes, "touch"):
            total_notes += notes.touch

        # 计算容错
        # 每个 TAP GREAT 损失 0.5% 的单 note 分数
        # 每个 BREAK GREAT 损失 0.5% ~ 2.5%（取决于 miss 数量）
        per_note = 100.0 / total_notes
        gap = 100.5 - target
        if gap < 0:
            yield event.plain_result("目标超过 100.5%，无法计算。")
            return

        max_great = int(gap / (per_note * 0.5))

        label = DIFF_INDEX_TO_LABEL.get(diff_idx, str(diff_idx))
        yield event.plain_result(
            f"🎵 {music.title} [{label}]\n"
            f"目标: {target}%\n"
            f"总 Note 数: {total_notes}\n"
            f"允许 TAP GREAT: ≤ {max_great} 个\n"
            f"（每 GREAT 损失 {per_note * 0.5:.3f}%）"
        )

    except Exception as e:
        logger.exception("分数线计算异常")
        yield event.plain_result(f"计算失败：{e}")


async def mai_score_calc_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """分数计算：X的Y是多少分。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^([\d.]+)的([\d.]+)是多少分$", text)
        if not m:
            yield event.plain_result("用法：<定数>的<达成率>是多少分")
            return

        ds = float(m.group(1))
        achievements = float(m.group(2))
        ra = data_mgr.compute_ra(ds, achievements)

        yield event.plain_result(
            f"定数 {ds} 达成率 {achievements}% = Ra {ra}"
        )

    except Exception as e:
        yield event.plain_result(f"计算失败：{e}")


async def mai_ranking_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    **_: Any,
):
    """查看排行榜。"""
    try:
        ranking = await api.rating_ranking()
        if not ranking:
            yield event.plain_result("排行榜数据为空。")
            return

        lines = ["🏆 Rating 排行榜 (Top 30)"]
        for i, u in enumerate(ranking[:30], 1):
            lines.append(f"{i:2d}. {u.username} — {u.ra}")

        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("排行榜查询异常")
        yield event.plain_result(f"查询失败：{e}")


async def mai_my_ranking_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    qq: int | None = None,
    **_: Any,
):
    """查看我的排名。"""
    try:
        if qq is None:
            qq = _extract_qq_from_at(event)
        user_info = await api.query_user_b50(qqid=qq)
        ranking = await api.rating_ranking()

        position = None
        for i, u in enumerate(ranking, 1):
            if u.username == user_info.username or u.username == user_info.nickname:
                position = i
                break

        if position:
            yield event.plain_result(
                f"📊 {user_info.nickname or user_info.username}\n"
                f"Rating: {user_info.rating}\n"
                f"排名: 第 {position} 名"
            )
        else:
            yield event.plain_result(
                f"📊 {user_info.nickname or user_info.username}\n"
                f"Rating: {user_info.rating}\n"
                f"未进入排行榜"
            )

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("排名查询异常")
        yield event.plain_result(f"查询失败：{e}")


# ================================================================
# 落雪查分器 (Lxns) — maimai DX B50 / minfo
# ================================================================


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
            song_data = await lxns.mai_song_list()
            for s in song_data.get("songs", []):
                sid = int(s["id"])
                for diff in s.get("difficulties", {}).get("standard", []):
                    ds_map[(sid, diff["difficulty"])] = diff["level_value"]
                for diff in s.get("difficulties", {}).get("dx", []):
                    ds_map[(sid, diff["difficulty"])] = diff["level_value"]
            logger.info(f"落雪歌曲定数加载: {len(ds_map)} 条")
        except Exception as e:
            logger.warning(f"落雪歌曲数据加载失败: {e}")
            yield event.plain_result("⚠️ 从落雪获取定数信息失败，将使用本地数据（部分歌曲定数可能缺失）。")
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

        # 获取玩家信息：OAuth > QQ 开发者 API > 好友码
        player = None
        friend_code = None
        use_oauth = False

        if lxns._user_token:
            try:
                player = await lxns.oauth_get_player(lxns._user_token, "maimai")
                friend_code = player.get("friend_code")
                use_oauth = True
            except Exception as e:
                logger.warning(f"落雪 OAuth 查询失败: {e}")

        if not player and qq:
            player = await lxns.mai_player_by_qq(qq)
            friend_code = player.get("friend_code")
        elif not player and query and query.isdigit():
            friend_code = int(query)
            player = await lxns.mai_player_by_fc(friend_code)

        if not player or not friend_code:
            yield event.plain_result(
                "未找到玩家。请先执行 `绑定QQ <QQ号>` 绑定，或使用 `绑定落雪` 授权。"
            )
            return

        # 获取 B50
        if use_oauth:
            bests_data = await lxns.oauth_get_bests(lxns._user_token, "maimai")
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
    music_data: MusicDataManager | None = None,
    **_: Any,
):
    """落雪 maimai DX 单曲成绩查询。"""
    try:
        args = event.get_message_str().strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：maiminfo <歌曲名/ID/别名>")
            return

        query = args[1].strip()

        # 通过别名解析真实歌名/ID
        resolved_name = None
        resolved_id = None
        if music_data:
            m = music_data.music_list.by_id(query)
            if m:
                resolved_id = int(m.id)
                resolved_name = m.title
            else:
                results = music_data.find_music_by_keyword(query)
                if not results:
                    results = music_data.find_music_by_alias(query)
                if results:
                    resolved_id = int(results[0].id)
                    resolved_name = results[0].title

        # 获取玩家信息：OAuth > QQ 开发者 API
        fc = None
        use_oauth = False
        if lxns._user_token:
            try:
                player = await lxns.oauth_get_player(lxns._user_token, "maimai")
                fc = player.get("friend_code")
                use_oauth = True
            except Exception as e:
                logger.warning(f"落雪 OAuth 查询失败: {e}")
        if not fc and qq:
            player = await lxns.mai_player_by_qq(qq)
            fc = player.get("friend_code")
        if not fc:
            yield event.plain_result("未找到玩家。请先执行 `绑定QQ <QQ号>` 绑定。")
            return

        # 获取单曲成绩
        search_id = resolved_id or (int(query) if query.isdigit() else None)
        search_name = resolved_name or (None if query.isdigit() else query)

        if use_oauth:
            all_scores = await lxns.oauth_get_scores(lxns._user_token, "maimai")
            if search_id:
                score = next((s for s in all_scores if s.get("id") == search_id), None)
            elif search_name:
                q = search_name.lower()
                score = next((s for s in all_scores if q in s.get("song_name", "").lower()), None)
            else:
                score = None
            if not score:
                yield event.plain_result(f"未找到歌曲「{query}」的成绩记录。")
                return
        else:
            params = {}
            if search_id:
                params["song_id"] = search_id
            elif search_name:
                params["song_name"] = search_name
            else:
                params["song_name"] = query
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
