"""别名命令：别名管理、投票、查询、WebSocket 推送。"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from ..errors import MaimaiError, describe_error
from ..mai_data import MusicDataManager

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..api_client import MaimaiAPI


async def update_alias_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """更新别名库。"""
    try:
        await data_mgr.load_alias_data()
        yield event.plain_result(f"✅ 别名库已更新，共 {len(data_mgr.alias_list)} 条。")
    except Exception as e:
        yield event.plain_result(f"更新失败：{e}")


async def alias_query_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """查询歌曲别名：X有什么别名。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(?:id\s?)?(.+)\s有什么别[名称]$", text)
        if not m:
            return

        query = m.group(1).strip()
        music = data_mgr.music_list.by_id(query)
        if not music:
            results = data_mgr.find_music_by_keyword(query)
            if results:
                music = results[0]
            else:
                yield event.plain_result("未找到匹配的歌曲。")
                return

        aliases = data_mgr.get_aliases_for_music(music.id)
        if aliases:
            yield event.plain_result(
                f"🎵 {music.title} (ID:{music.id}) 的别名：\n" +
                "\n".join(f"  - {a}" for a in aliases)
            )
        else:
            yield event.plain_result(f"🎵 {music.title} 暂无别名。")

    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def alias_apply_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    data_mgr: MusicDataManager,
    uuid: str = "",
    **_: Any,
):
    """提交别名申请。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(添加别名|增加别名|增添别名|添加别称)\s+(.+)$", text)
        if not m:
            return

        args = m.group(2).strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：添加别名 <歌曲ID/名称> <别名>")
            return

        query, alias_name = args[0].strip(), args[1].strip()
        music = data_mgr.music_list.by_id(query)
        if not music:
            results = data_mgr.find_music_by_keyword(query)
            if results:
                music = results[0]
            else:
                yield event.plain_result("未找到匹配的歌曲。")
                return

        user_id = int(event.get_sender_id())
        group_id = int(event.get_group_id() or 0)

        result = await api.post_alias(int(music.id), alias_name, user_id, group_id, uuid)
        yield event.plain_result(f"✅ 别名申请已提交：{music.title} -> {alias_name}")

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        logger.exception("提交别名异常")
        yield event.plain_result(f"提交失败：{e}")


async def alias_local_apply_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """添加本地别名。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(添加本地别名|添加本地别称)\s+(.+)$", text)
        if not m:
            return

        args = m.group(2).strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法：添加本地别名 <歌曲ID/名称> <别名>")
            return

        query, alias_name = args[0].strip(), args[1].strip()
        music = data_mgr.music_list.by_id(query)
        if not music:
            results = data_mgr.find_music_by_keyword(query)
            if results:
                music = results[0]
            else:
                yield event.plain_result("未找到匹配的歌曲。")
                return

        # 保存到本地别名文件
        local_alias = await data_mgr._read_json("local_alias.json") or {}
        song_id_str = str(music.id)
        if song_id_str not in local_alias:
            local_alias[song_id_str] = []
        if alias_name.lower() not in [a.lower() for a in local_alias[song_id_str]]:
            local_alias[song_id_str].append(alias_name.lower())
            await data_mgr._write_json("local_alias.json", local_alias)
            # 更新内存中的别名列表
            for a in data_mgr.alias_list.by_id(music.id):
                a.Alias.append(alias_name.lower())
                break
            yield event.plain_result(f"✅ 本地别名已添加：{music.title} -> {alias_name}")
        else:
            yield event.plain_result("该别名已存在。")

    except Exception as e:
        yield event.plain_result(f"添加失败：{e}")


async def alias_agree_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    **_: Any,
):
    """同意别名投票。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(同意别名|同意别称)\s+(.+)$", text)
        if not m:
            return

        tag = m.group(2).strip()
        user_id = int(event.get_sender_id())
        result = await api.post_agree_user(tag, user_id)
        yield event.plain_result(f"✅ 已投票：{result}")

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        yield event.plain_result(f"投票失败：{e}")


async def alias_status_handler(
    event: AstrMessageEvent,
    api: MaimaiAPI,
    **_: Any,
):
    """查看当前投票。"""
    try:
        statuses = await api.get_alias_status()
        if not statuses:
            yield event.plain_result("当前没有进行中的别名投票。")
            return

        lines = ["📋 当前别名投票"]
        for s in statuses:
            lines.append(f"  [{s.Tag}] {s.Name} -> {s.ApplyAlias} (票数:{s.Votes})")

        yield event.plain_result("\n".join(lines))

    except MaimaiError as e:
        yield event.plain_result(describe_error(e))
    except Exception as e:
        yield event.plain_result(f"查询失败：{e}")


async def alias_push_handler(
    event: AstrMessageEvent,
    group_store,
    **_: Any,
):
    """开启/关闭别名推送（群级）。"""
    try:
        text = event.get_message_str().strip()
        m = re.match(r"^(开启|关闭)(别名推送|别称推送)$", text)
        if not m:
            return

        enable = m.group(1) == "开启"
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此命令只能在群聊中使用。")
            return

        await group_store.toggle_alias_push(group_id, enable)
        if enable:
            # 记录群的 unified_msg_origin，供别名推送广播使用
            session = getattr(event, "unified_msg_origin", "") or ""
            if session:
                await group_store.set_and_save_alias_push_session(group_id, session)
        else:
            await group_store.remove_alias_push_session(group_id)
        status = "开启" if enable else "关闭"
        yield event.plain_result(f"✅ 群别名推送已{status}。")

    except Exception as e:
        yield event.plain_result(f"操作失败：{e}")


# --- WebSocket 别名推送服务 ---

class AliasPushService:
    """WebSocket 别名推送后台服务。"""

    def __init__(self, api: MaimaiAPI, uuid: str) -> None:
        self.api = api
        self.uuid = uuid
        self._task: asyncio.Task | None = None

    async def start(self, context, group_store) -> None:
        """启动 WebSocket 推送。"""
        if self._task:
            return
        self._task = asyncio.create_task(self._run(context, group_store))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._task = None

    async def _run(self, context, group_store) -> None:
        """WebSocket 推送主循环。"""
        try:
            import aiohttp
        except ImportError:
            logger.warning("aiohttp 未安装，别名推送不可用")
            return

        url = f"wss://www.yuzuchan.moe/api/maimaidx/ws/{self.uuid}"
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url) as ws:
                        logger.info("别名推送 WebSocket 已连接")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_message(msg.data, context, group_store)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
            except Exception as e:
                logger.warning(f"别名推送 WebSocket 断开: {e}，60秒后重连")
            await asyncio.sleep(60)

    async def _handle_message(self, data: str, context, group_store) -> None:
        """处理推送消息。"""
        try:
            import json
            from ..models import PushAliasStatus
            msg = json.loads(data)
            status = PushAliasStatus.model_validate(msg)
            text = f"🔔 别名{status.Type}: {status.Status.Name}"
            if hasattr(status.Status, "ApplyAlias"):
                text += f" -> {status.Status.ApplyAlias}"

            await self._broadcast(context, group_store, text)
        except Exception as e:
            logger.warning(f"处理别名推送消息失败: {e}")

    async def _broadcast(self, context, group_store, text: str) -> None:
        """广播别名推送文本到所有已开启推送的群。"""
        sessions = group_store.get_all_alias_push_sessions()
        if not sessions:
            return

        try:
            from astrbot.api.message_components import Plain
            from astrbot.core.message.message_event_result import MessageChain
        except ImportError:
            logger.warning("无法导入 AstrBot 消息组件，跳过广播")
            return

        for group_id, session in sessions.items():
            if not group_store.is_alias_push_enabled(group_id):
                continue
            if not session:
                continue
            try:
                chain = MessageChain(chain=[Plain(text)])
                await context.send_message(session, chain)
            except Exception as e:
                # qq_official 等平台不支持主动发送；单群失败不影响其他群
                logger.debug(f"别名推送广播到 {group_id} 失败: {e}")
