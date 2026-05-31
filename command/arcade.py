"""机厅命令：添加/删除/修改/搜索机厅、订阅、排队管理。"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

from ..arcade_data import ArcadeDataManager

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


async def add_arcade_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """添加机厅。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(添加机厅|新增机厅)\s+(.+)$", text)
        if not m:
            return

        args = m.group(2).strip().split("|")
        name = args[0].strip()
        address = args[1].strip() if len(args) > 1 else ""
        machine_count = int(args[2].strip()) if len(args) > 2 else 0
        aliases = [a.strip() for a in args[3].split(",")] if len(args) > 3 and args[3].strip() else []

        await arcade_mgr.add_arcade(name, address, machine_count, aliases)
        yield event.plain_result(f"✅ 机厅已添加：{name}")

    except Exception as e:
        yield event.plain_result(f"添加失败：{e}")


async def delete_arcade_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """删除机厅。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(删除机厅|移除机厅)\s+(.+)$", text)
        if not m:
            return

        name = m.group(2).strip()
        if await arcade_mgr.remove_arcade(name):
            yield event.plain_result(f"✅ 机厅已删除：{name}")
        else:
            yield event.plain_result(f"未找到机厅：{name}")

    except Exception as e:
        yield event.plain_result(f"删除失败：{e}")


async def modify_arcade_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """修改机厅。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(修改机厅|编辑机厅)\s+(.+)$", text)
        if not m:
            return

        args = m.group(2).strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：修改机厅 <机厅名> <属性=值>")
            return

        name = args[0].strip()
        props = {}
        for pair in args[1].split():
            if "=" in pair:
                k, v = pair.split("=", 1)
                if k == "台数":
                    props["machine_count"] = int(v)
                elif k == "地址":
                    props["address"] = v

        if await arcade_mgr.modify_arcade(name, **props):
            yield event.plain_result(f"✅ 机厅已修改：{name}")
        else:
            yield event.plain_result(f"未找到机厅：{name}")

    except Exception as e:
        yield event.plain_result(f"修改失败：{e}")


async def arcade_alias_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """添加/删除机厅别名。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(添加机厅别名|删除机厅别名)\s+(.+)$", text)
        if not m:
            return

        args = m.group(2).strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：添加/删除机厅别名 <机厅名> <别名>")
            return

        name, alias_name = args[0].strip(), args[1].strip()
        is_add = "添加" in m.group(1)

        if is_add:
            ok = await arcade_mgr.add_arcade_alias(name, alias_name)
            msg = f"✅ 别名已添加：{alias_name}" if ok else f"未找到机厅：{name}"
        else:
            ok = await arcade_mgr.remove_arcade_alias(name, alias_name)
            msg = f"✅ 别名已删除：{alias_name}" if ok else f"未找到机厅：{name}"

        yield event.plain_result(msg)

    except Exception as e:
        yield event.plain_result(f"操作失败：{e}")


async def search_arcade_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """搜索机厅。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(查找机厅|查询机厅|机厅查找|机厅查询|搜素机厅|机厅搜素)\s+(.+)$", text)
        if not m:
            return

        keyword = m.group(2).strip()
        results = arcade_mgr.search_arcades(keyword)

        if not results:
            yield event.plain_result(f"未找到包含「{keyword}」的机厅。")
            return

        lines = [f"找到 {len(results)} 个机厅："]
        for a in results:
            mc = f"（{a.machine_count}台）" if a.machine_count else ""
            addr = f" @ {a.address}" if a.address else ""
            aliases = f" [{', '.join(a.aliases)}]" if a.aliases else ""
            lines.append(f"  • {a.name}{mc}{addr}{aliases}")

        yield event.plain_result("\n".join(lines))

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def subscribe_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """订阅/取消订阅机厅。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(订阅机厅|取消订阅机厅|取消订阅)\s+(.+)$", text)
        if not m:
            return

        name = m.group(2).strip()
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此命令只能在群聊中使用。")
            return

        is_sub = "取消" not in m.group(1)
        if is_sub:
            ok = await arcade_mgr.subscribe(group_id, name)
            msg = f"✅ 已订阅：{name}" if ok else f"未找到机厅：{name}"
        else:
            ok = await arcade_mgr.unsubscribe(group_id, name)
            msg = f"✅ 已取消订阅：{name}" if ok else f"未找到机厅：{name}"

        yield event.plain_result(msg)

    except Exception as e:
        yield event.plain_result(f"操作失败：{e}")


async def check_subscribe_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """查看订阅。"""
    group_id = event.get_group_id()
    if not group_id:
        yield event.plain_result("此命令只能在群聊中使用。")
        return

    subs = arcade_mgr.get_subscriptions(group_id)
    if not subs:
        yield event.plain_result("当前群未订阅任何机厅。")
        return

    lines = ["📋 当前群订阅的机厅："]
    for name in subs:
        queue = arcade_mgr.get_queue(name)
        if queue:
            lines.append(f"  • {name}: {queue.person_count}人 {queue.card_count}卡")
        else:
            lines.append(f"  • {name}: 暂无排队数据")

    yield event.plain_result("\n".join(lines))


async def arcade_person_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """设置/加/减人数。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(
            r"^(.+?)?\s?(设置|设定|＝|=|增加|添加|加|＋|\+|减少|降低|减|－|-)\s?(\d+|＋|\+|－|-)(人|卡)?$",
            text,
        )
        if not m:
            return

        name = (m.group(1) or "").strip()
        op = m.group(2)
        val_str = m.group(3).replace("＋", "+").replace("－", "-").replace("＝", "=")
        unit = m.group(4) or "人"

        if not name:
            group_id = event.get_group_id()
            subs = arcade_mgr.get_subscriptions(group_id) if group_id else []
            if len(subs) == 1:
                name = subs[0]
            else:
                yield event.plain_result("请指定机厅名称。")
                return

        val = int(val_str)
        is_set = op in ("设置", "设定", "=", "＝")
        is_card = unit == "卡"

        if is_set:
            kwargs = {"set_card": val} if is_card else {"set_person": val}
        else:
            is_add = op in ("增加", "添加", "加", "＋", "+")
            delta = val if is_add else -val
            kwargs = {"card_delta": delta} if is_card else {"person_delta": delta}

        queue = await arcade_mgr.update_queue(
            name, operator=event.get_sender_name() or event.get_sender_id(), **kwargs
        )
        if queue:
            yield event.plain_result(
                f"✅ {queue.arcade_name}: {queue.person_count}人 {queue.card_count}卡"
            )
        else:
            yield event.plain_result(f"未找到机厅：{name}")

    except Exception as e:
        yield event.plain_result(f"操作失败：{e}")


async def arcade_query_handler(
    event: AstrMessageEvent,
    arcade_mgr: ArcadeDataManager,
    **_: Any,
):
    """查询排队：机厅几人 / jtj / X有几人 / jr。"""
    try:
        text = event.get_message_str().strip()
        group_id = event.get_group_id()

        # 通用查询：机厅几人 / jtj
        if re.match(r"^(机厅几人|jtj)$", text, re.I):
            if not group_id:
                yield event.plain_result("此命令只能在群聊中使用。")
                return
            queues = arcade_mgr.get_queues_for_group(group_id)
            if not queues:
                yield event.plain_result("当前群未订阅任何机厅。")
                return
            lines = ["🕹️ 机厅排队状态"]
            for q in queues:
                lines.append(f"  {q.arcade_name}: {q.person_count}人 {q.card_count}卡")
            yield event.plain_result("\n".join(lines))
            return

        # 指定机厅查询：X有几人 / jr
        m = re.match(r"^(.+?)(有多少人|有几人|有几卡|多少人|多少卡|几人|jr|几卡)$", text, re.I)
        if m:
            name = m.group(1).strip()
            if not name:
                # 查询所有订阅
                if group_id:
                    queues = arcade_mgr.get_queues_for_group(group_id)
                    if queues:
                        lines = ["🕹️ 机厅排队状态"]
                        for q in queues:
                            lines.append(f"  {q.arcade_name}: {q.person_count}人 {q.card_count}卡")
                        yield event.plain_result("\n".join(lines))
                    else:
                        yield event.plain_result("当前群未订阅任何机厅。")
                return

            queue = arcade_mgr.get_queue(name)
            if queue:
                yield event.plain_result(
                    f"{queue.arcade_name}: {queue.person_count}人 {queue.card_count}卡"
                )
            else:
                yield event.plain_result(f"未找到机厅：{name}")
            return

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")
