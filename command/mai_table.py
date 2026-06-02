"""牌桌命令：定数表、完成表、推分、版牌进度、等级进度、分数列表。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error
from ..mai_data import MusicDataManager, achievements_label, LEVEL_LIST, DIFF_INDEX_TO_LABEL, music_by_plan

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..api_client import MaimaiAPI


async def mai_rating_table_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """X定数表。"""
    text = event.get_message_str().strip()
    m = re.match(r"^(?!更新)(.+?)定数表$", text)
    if not m:
        return

    level = m.group(1).strip()
    if level not in LEVEL_LIST:
        yield event.plain_result(f"无效等级。可用：{', '.join(LEVEL_LIST)}")
        return

    plan = music_by_plan(data_mgr.music_list, level)
    if not plan:
        yield event.plain_result(f"没有 {level} 等级的歌曲。")
        return

    lines = [f"# 📋 {level} 定数表\n"]
    by_ds: dict[float, list[str]] = {}
    for mid, info in plan.items():
        if isinstance(info, dict):
            for idx, rm in info.items():
                music = data_mgr.music_list.by_id(rm.id)
                title = music.title if music else str(rm.id)
                by_ds.setdefault(rm.ds, []).append(f"| {rm.id} | {title} |")
        else:
            music = data_mgr.music_list.by_id(info.id)
            title = music.title if music else str(info.id)
            by_ds.setdefault(info.ds, []).append(f"| {info.id} | {title} |")

    for ds in sorted(by_ds.keys()):
        songs = by_ds[ds]
        lines.append(f"## {ds}（{len(songs)}首）\n")
        lines.append("| ID | 曲名 |")
        lines.append("|-----|------|")
        lines.extend(songs)
        lines.append("")

    yield event.make_result().use_markdown(True).message("\n".join(lines))


async def mai_rise_score_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """推分建议。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^我要在?([0-9]+\+?)?[上加\+]([0-9]+)?分\s?(.+)?$", text)
        if not m:
            yield event.plain_result("用法：我要在<等级>上<N>分")
            return

        level = m.group(1)
        target_gain = int(m.group(2)) if m.group(2) else 1
        username = m.group(3)

        from ..utils import extract_at_targets
        qq = None
        at_targets = extract_at_targets(event)
        if at_targets:
            try:
                qq = int(at_targets[0])
            except (ValueError, TypeError):
                pass

        user_info = await api.query_user_b50(qqid=qq, username=username)
        if not user_info.charts:
            yield event.plain_result("未找到游玩记录。")
            return

        # 收集所有成绩
        all_charts = []
        if user_info.charts.sd:
            all_charts.extend(user_info.charts.sd)
        if user_info.charts.dx:
            all_charts.extend(user_info.charts.dx)

        # 按 Ra 排序，找到可以提升的歌曲
        all_charts.sort(key=lambda c: c.ra)
        suggestions = []
        current_ra = sum(c.ra for c in all_charts[:50]) if len(all_charts) >= 50 else sum(c.ra for c in all_charts)

        for chart in all_charts[:50]:
            music = data_mgr.music_list.by_id(chart.song_id)
            if not music:
                continue
            for i, ds in enumerate(music.ds):
                if level and music.level[i] != level:
                    continue
                new_ra = data_mgr.compute_ra(ds, chart.achievements + 1.0)
                if new_ra > chart.ra:
                    gain = new_ra - chart.ra
                    suggestions.append((gain, chart.title, music.level[i], chart.ra, new_ra))

        suggestions.sort(key=lambda x: -x[0])

        if not suggestions:
            yield event.plain_result("未找到可提升的歌曲。")
            return

        lines = [f"📈 推分建议（目标 +{target_gain}）"]
        total_gain = 0
        for gain, title, lv, old_ra, new_ra in suggestions[:20]:
            if total_gain >= target_gain:
                break
            lines.append(f"  [{lv}] {title}: {old_ra} → {new_ra} (+{gain})")
            total_gain += gain

        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("推分建议异常")
        yield event.plain_result(f"查询失败：{e}")


async def mai_plate_progress_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """版牌进度。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(
            r"^([真超檄橙暁晓桃櫻樱紫菫堇白雪輝辉舞霸熊華华爽煌星宙祭祝双宴镜彩])"
            r"([極极将舞神者]舞?)进度\s?(.+)?$",
            text,
        )
        if not m:
            return

        version_char = m.group(1)
        rank_char = m.group(2)
        username = m.group(3)

        # 映射版本名
        version_map = {
            "真": "maimai", "超": "maimai PLUS", "檄": "maimai GreeN",
            "橙": "maimai GreeN PLUS", "暁": "maimai ORANGE", "晓": "maimai ORANGE PLUS",
            "桃": "maimai PiNK", "櫻": "maimai MURASAKi", "樱": "maimai MURASAKi PLUS",
            "紫": "maimai MiLK", "菫": "miLK PLUS", "堇": "miLK PLUS",
            "白": "maimai FiNALE", "雪": "maimai でらっくす",
            "輝": "maimai でらっくす PLUS", "辉": "maimai でらっくす PLUS",
            "舞": "maimai でらっくす Splash", "霸": "maimai でらっくす Splash PLUS",
            "熊": "maimai でらっくす UNiVERSE", "華": "maimai でらっくす UNiVERSE PLUS",
            "华": "maimai でらっくす UNiVERSE PLUS",
            "爽": "maimai でらっくす FESTiVAL", "煌": "maimai でらっくす FESTiVAL PLUS",
            "星": "maimai でらっくす BUDDiES", "宙": "maimai でらっくす BUDDiES PLUS",
            "祭": "maimai でらっくす PRiSM", "祝": "maimai でらっくす PRiSM PLUS",
            "双": "maimai でらっくす PRiSM", "宴": "maimai でらっくす PRiSM PLUS",
            "镜": "maimai でらっくす PRiSM", "彩": "maimai でらっくす PRiSM PLUS",
        }
        rank_map = {"極": "極", "极": "極", "将": "将", "舞者": "舞者", "神": "神", "舞": "舞"}

        version = version_map.get(version_char)
        rank = rank_map.get(rank_char, rank_char)
        if not version:
            yield event.plain_result("未识别的版本。")
            return

        from ..utils import extract_at_targets
        qq = None
        at_targets = extract_at_targets(event)
        if at_targets:
            try:
                qq = int(at_targets[0])
            except (ValueError, TypeError):
                pass

        records = await api.query_user_plate(qqid=qq, username=username, version=[version])
        total = len(records)
        completed = sum(1 for r in records if _check_plate_rank(r, rank))

        pct = (completed / total * 100) if total > 0 else 0
        yield event.plain_result(
            f"📋 {version_char}{rank_char}进度\n"
            f"已完成: {completed}/{total} ({pct:.1f}%)\n"
            f"未完成: {total - completed}"
        )

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("版牌进度异常")
        yield event.plain_result(f"查询失败：{e}")


def _check_plate_rank(record, rank: str) -> bool:
    """检查成绩是否达到版牌等级要求。"""
    ach = record.achievements
    fc = record.fc
    if rank == "極":
        return ach >= 100.0
    if rank == "将":
        return ach >= 100.5
    if rank == "舞者":
        return fc in ("ap", "app")
    if rank == "神":
        return fc in ("ap", "app") and ach >= 100.5
    if rank == "舞":
        return ach >= 100.5
    return False


async def mai_level_progress_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """等级进度。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(
            r"^([0-9]+\+?)\s?([abcdsfxp\+]+)\s?([一-龥]+)?进度\s?([0-9]+)?\s?(.+)?$",
            text, re.I,
        )
        if not m:
            return

        level = m.group(1)
        rank_str = m.group(2).lower()
        filter_status = m.group(3)
        page = int(m.group(4)) if m.group(4) else 1
        username = m.group(5)

        from ..utils import extract_at_targets
        qq = None
        at_targets = extract_at_targets(event)
        if at_targets:
            try:
                qq = int(at_targets[0])
            except (ValueError, TypeError):
                pass

        user_info = await api.query_user_b50(qqid=qq, username=username)
        if not user_info.charts:
            yield event.plain_result("未找到游玩记录。")
            return

        # 收集该等级的所有谱面
        level_songs = []
        for music in data_mgr.music_list:
            for i, lv in enumerate(music.level):
                if lv == level and int(music.id) < 100000:
                    level_songs.append((music, i))

        # 匹配用户成绩
        all_charts = []
        if user_info.charts.sd:
            all_charts.extend(user_info.charts.sd)
        if user_info.charts.dx:
            all_charts.extend(user_info.charts.dx)

        chart_map = {(c.song_id, c.level_index): c for c in all_charts}

        results = []
        for music, idx in level_songs:
            chart = chart_map.get((int(music.id), idx))
            ach = chart.achievements if chart else 0
            results.append((music, idx, ach))

        results.sort(key=lambda x: -x[2])

        lines = [f"📊 {level} {rank_str.upper()} 进度 (第{page}页)"]
        start = (page - 1) * 30
        for music, idx, ach in results[start:start + 30]:
            label = DIFF_INDEX_TO_LABEL.get(idx, str(idx))
            status = achievements_label(ach) if ach > 0 else "未游玩"
            lines.append(f"  [{label}] {music.title}: {ach:.4f}% ({status})")

        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("等级进度异常")
        yield event.plain_result(f"查询失败：{e}")


async def mai_level_achievement_list_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """分数列表。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^([0-9]+\.?[0-9]?\+?)分数列表\s?([0-9]+)?\s?(.+)?$", text)
        if not m:
            return

        level = m.group(1)
        page = int(m.group(2)) if m.group(2) else 1
        username = m.group(3)

        from ..utils import extract_at_targets
        qq = None
        at_targets = extract_at_targets(event)
        if at_targets:
            try:
                qq = int(at_targets[0])
            except (ValueError, TypeError):
                pass

        user_info = await api.query_user_b50(qqid=qq, username=username)
        if not user_info.charts:
            yield event.plain_result("未找到游玩记录。")
            return

        all_charts = []
        if user_info.charts.sd:
            all_charts.extend(user_info.charts.sd)
        if user_info.charts.dx:
            all_charts.extend(user_info.charts.dx)

        # 过滤指定等级
        matching = [c for c in all_charts if c.level == level]
        matching.sort(key=lambda c: -c.achievements)

        lines = [f"📊 {level} 分数列表 (第{page}页)"]
        start = (page - 1) * 30
        for i, c in enumerate(matching[start:start + 30], start + 1):
            lines.append(f"  {i}. {c.title}: {c.achievements:.4f}% | Ra:{c.ra}")

        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("分数列表异常")
        yield event.plain_result(f"查询失败：{e}")
