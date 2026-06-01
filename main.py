"""插件入口：注册、命令路由、生命周期管理。"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.all import register
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.event.filter import EventMessageType, command, event_message_type
from astrbot.api.star import Context, Star, StarTools

from .api_client import MaimaiAPI
from .arcade_data import ArcadeDataManager
from .lxns_client import LxnsAPI
from .chunithm_data import ChuDataManager
from .command.chunithm import chu_b30_handler, chu_minfo_handler, chu_search_handler, chu_id_handler
from .command.lxns_mai import lxns_mai_b50_handler, lxns_mai_minfo_handler
from .command.alias import (
    AliasPushService, alias_agree_handler, alias_apply_handler,
    alias_global_push_handler, alias_local_apply_handler, alias_push_handler,
    alias_query_handler, alias_status_handler, update_alias_handler,
)
from .command.arcade import (
    add_arcade_handler, arcade_alias_handler, arcade_person_handler,
    arcade_query_handler, check_subscribe_handler, delete_arcade_handler,
    modify_arcade_handler, search_arcade_handler, subscribe_handler,
)
from .command.guess import (
    guess_music_handler, guess_pic_handler, guess_solve_handler,
    reset_guess_handler,
)
from .command.help import help_handler
from .command.score import (
    b50_handler, ginfo_handler, minfo_handler, my_ranking_handler,
    ranking_handler, score_calc_handler, score_line_handler,
)
from .command.search import (
    query_by_id_handler, search_alias_handler, search_artist_handler,
    search_base_handler, search_bpm_handler, search_charter_handler,
    search_music_handler,
)
from .command.table import (
    level_achievement_list_handler, level_progress_handler,
    plate_progress_handler, rating_table_handler, rise_score_handler,
)
from .errors import MaimaiError, describe_error
from .music_data import MusicDataManager
from .storage import GroupConfigStore, UserStore
from .utils import get_platform_adapter_name, is_group_message

VALID_GAMES = {"maimai", "chunithm"}
GAME_LABELS = {"maimai": "maimai DX", "chunithm": "CHUNITHM"}


@register(
    "astrbot_plugin_hachikei_chunimai",
    "TheSixPasserby",
    "maimai DX / CHUNITHM 综合助手：查分、搜歌、猜歌、牌桌、别名、机厅排队。",
    "0.1.0",
    "",
)
class MaimaiPlugin(Star):
    """maimai DX / CHUNITHM 综合助手插件。"""

    def __init__(self, context: Context, config: AstrBotConfig | dict) -> None:
        super().__init__(context)
        self.config = config if isinstance(config, dict) else {}

        data_dir = StarTools.get_data_dir(plugin_name="astrbot_plugin_hachikei_chunimai")

        # 配置
        self.bot_name: str = self.config.get("bot_name", "mai-bot")
        self.enable_reply: bool = self.config.get("enable_reply", True)
        self.timeout: int = self._int_config("request_timeout_seconds", 30)

        # 子系统
        self.api = MaimaiAPI(timeout=self.timeout)
        self.lxns = LxnsAPI(timeout=self.timeout)
        self.user_store = UserStore(data_dir)
        self.group_store = GroupConfigStore(data_dir)
        self.music_data = MusicDataManager(self.api, data_dir)
        self.chu_data = ChuDataManager(self.lxns, data_dir)
        self.arcade_data = ArcadeDataManager(data_dir)
        self.alias_push = AliasPushService(self.api, self.config.get("alias_push_uuid", ""))

        # 管理员 ID
        self.admin_ids: list[str] = []
        try:
            bot_config = context.get_config()
            self.admin_ids = [str(a) for a in bot_config.get("admins_id", [])]
        except Exception:
            pass

    def _int_config(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except (ValueError, TypeError):
            return default

    async def initialize(self) -> None:
        """异步初始化：配置 API、加载数据。"""
        token = self.config.get("maimaidxtoken", "")
        proxy = bool(self.config.get("maimai_http_proxy", ""))
        self.api.configure(token=token, proxy=proxy)

        try:
            await self.music_data.load_all()
        except Exception as e:
            logger.error(f"加载歌曲数据失败: {e}")

        # Lxns + CHUNITHM
        lxns_key = self.config.get("lxns_dev_key", "")
        lxns_token = self.config.get("lxns_user_token", "")
        self.lxns.configure(dev_key=lxns_key, user_token=lxns_token)
        try:
            await self.chu_data.load_all()
        except Exception as e:
            logger.error(f"加载 CHUNITHM 数据失败: {e}")

        # 启动别名推送
        if self.config.get("enable_alias_push") and self.config.get("alias_push_uuid"):
            await self.alias_push.start(self.context, self.group_store)

        logger.info("maimai DX / CHUNITHM 插件已加载")

    async def terminate(self) -> None:
        """清理资源。"""
        await self.alias_push.stop()
        await self.api.close()
        await self.lxns.close()
        logger.info("插件已卸载")

    # --- 工具方法 ---

    @staticmethod
    def _message(text: str) -> MessageEventResult:
        return MessageEventResult().message(text)

    @staticmethod
    def _user_key(event: AstrMessageEvent) -> str:
        return f"{event.get_platform_name()}:{event.get_sender_id()}"

    @staticmethod
    def _table_name(game: str) -> str:
        """根据游戏返回表格名称：maimai -> B50, chunithm -> B30"""
        return "B30" if game == "chunithm" else "B50"

    def _group_id(self, event: AstrMessageEvent) -> str:
        """跨平台获取群/频道 ID。"""
        # 1. 标准方法
        gid = event.get_group_id()
        if gid:
            return str(gid)
        # 2. 直接读 message_obj 属性
        try:
            msg = event.message_obj
            for attr in ("group_id", "channel_id", "group_openid"):
                val = getattr(msg, attr, None)
                if val:
                    return str(val)
        except Exception:
            pass
        # 3. QQ 官方 API fallback: session_id 就是 group_openid
        try:
            sid = event.session_id
            if sid:
                return str(sid)
        except Exception:
            pass
        return ""

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        return event.get_sender_id() in self.admin_ids

    def _is_group_disabled(self, event: AstrMessageEvent) -> bool:
        gid = self._group_id(event)
        return bool(gid) and self.group_store.is_group_disabled(gid)

    def _resolve_game(self, event: AstrMessageEvent) -> str:
        """解析当前用户的游戏模式。优先级：个人设置 > 群默认 > maimai"""
        user_key = self._user_key(event)
        personal = self.user_store.get_game_mode(user_key)
        if personal:
            return personal
        gid = self._group_id(event)
        if gid:
            return self.group_store.get_group_game_mode(gid)
        return "maimai"

    # ================================================================
    # 游戏切换
    # ================================================================

    @command("game", alias={"切换游戏", "游戏模式"})
    async def _switch_game(self, event: AstrMessageEvent):
        """切换游戏模式。用法：
        game maimai       — 设置个人游戏模式
        game chunithm     — 设置个人游戏模式
        game reset        — 清除个人设置，跟随群规则
        game group maimai — (管理员) 设置群默认游戏
        game status       — 查看当前游戏模式
        """
        args = event.get_message_str().strip().split()
        # game / 切换游戏 / 游戏模式
        # args[0] 是命令名

        if len(args) < 2:
            current = self._resolve_game(event)
            label = GAME_LABELS.get(current, current)
            user_key = self._user_key(event)
            personal = self.user_store.get_game_mode(user_key)
            gid = self._group_id(event)
            group_default = self.group_store.get_group_game_mode(gid) if gid else "maimai"

            lines = [f"🎮 当前游戏: {label}"]
            if personal:
                lines.append(f"  来源: 个人设置 ({personal})")
            elif gid:
                lines.append(f"  来源: 群默认 ({group_default})")
            else:
                lines.append(f"  来源: 默认 (maimai)")
            lines.append("")
            lines.append("用法:")
            lines.append("  game maimai/chunithm — 设置个人游戏")
            lines.append("  game reset — 清除个人设置")
            lines.append("  game status — 查看详情")
            if self._is_admin(event):
                lines.append("  game group maimai/chunithm — 设置群默认")
            yield self._message("\n".join(lines))
            return

        sub = args[1].lower()

        # game status
        if sub == "status":
            current = self._resolve_game(event)
            label = GAME_LABELS.get(current, current)
            user_key = self._user_key(event)
            personal = self.user_store.get_game_mode(user_key)
            gid = self._group_id(event)
            group_default = self.group_store.get_group_game_mode(gid) if gid else "maimai"

            lines = [f"🎮 游戏模式详情"]
            lines.append(f"  生效: {label}")
            lines.append(f"  个人: {personal or '(未设置)'}")
            if gid:
                lines.append(f"  群默认: {group_default}")
            yield self._message("\n".join(lines))
            return

        # game reset
        if sub == "reset":
            user_key = self._user_key(event)
            await self.user_store.set_game_mode(user_key, "")
            yield self._message("✅ 已清除个人游戏设置，将跟随群规则。")
            return

        # game group <game> — 管理员设置群默认
        if sub == "group":
            if not self._is_admin(event):
                yield self._message("需要管理员权限。")
                return
            if len(args) < 3:
                yield self._message("用法: game group maimai/chunithm")
                return
            game = args[2].lower()
            if game not in VALID_GAMES:
                yield self._message(f"无效游戏。可选: {', '.join(VALID_GAMES)}")
                return
            gid = self._group_id(event)
            if not gid:
                yield self._message("此命令只能在群聊中使用。")
                return
            await self.group_store.set_group_game_mode(gid, game)
            label = GAME_LABELS.get(game, game)
            yield self._message(f"✅ 群默认游戏已设为 {label}。")
            return

        # game maimai/chunithm — 个人设置
        game = sub
        if game not in VALID_GAMES:
            yield self._message(f"无效游戏。可选: {', '.join(VALID_GAMES)}")
            return
        user_key = self._user_key(event)
        await self.user_store.set_game_mode(user_key, game)
        label = GAME_LABELS.get(game, game)
        yield self._message(f"✅ 个人游戏已设为 {label}。")

    # ================================================================
    # 查分器切换
    # ================================================================

    @command("switchprober", alias={"切换查分器", "更改查分器"})
    async def _switch_prober(self, event: AstrMessageEvent):
        """切换舞萌查分器。用法：更改查分器 水鱼/落雪"""
        full_text = event.get_message_str().strip()
        args = full_text.split(maxsplit=1)
        param = args[1].strip() if len(args) > 1 else ""

        prober_input = None
        for t in [full_text, param]:
            m = re.match(r"^(?:切换|更改)?(?:舞萌)?(?:查分器)?\s*(水鱼|落雪|divingfish|lxns)$", t, re.I)
            if m:
                prober_input = m.group(1).lower()
                break

        if not prober_input:
            yield self._message("用法：更改查分器 水鱼/落雪")
            return

        prober_map = {"水鱼": "divingfish", "落雪": "lxns", "divingfish": "divingfish", "lxns": "lxns"}
        prober = prober_map.get(prober_input)
        if not prober:
            yield self._message("无效查分器。可选：水鱼、落雪")
            return

        group_id = self._group_id(event)
        if not group_id:
            yield self._message("此命令只能在群聊中使用。")
            return

        await self.group_store.set_prober("maimai", prober, group_id)
        prober_label = "水鱼" if prober == "divingfish" else "落雪"
        yield self._message(f"✅ 舞萌查分器已切换为 {prober_label}。")

    def _get_prober(self, event: AstrMessageEvent, game: str) -> str:
        """获取当前群指定游戏的查分器。"""
        gid = self._group_id(event)
        return self.group_store.get_prober(game, gid)

    # ================================================================
    # 绑定 QQ
    # ================================================================

    @command("bindqq", alias={"绑定qq", "绑定QQ"})
    async def _bind_qq(self, event: AstrMessageEvent):
        args = event.get_message_str().strip().split()
        if len(args) < 2 or not args[1].isdigit():
            yield self._message("用法：bindqq <QQ号>\n绑定后查分命令将使用该 QQ 号查询。")
            return
        qq = args[1].strip()
        user_key = self._user_key(event)
        await self.user_store.set_qq(user_key, qq)
        yield self._message(f"✅ 已绑定 QQ: {qq}")

    def _get_qq(self, event: AstrMessageEvent) -> int | None:
        """获取用户的 QQ 号：优先从 @提及 获取，其次从绑定记录获取。"""
        # 1. 尝试从 @提及 获取
        try:
            from astrbot.api.message_components import At
            for comp in event.get_messages():
                if isinstance(comp, At):
                    return int(comp.qq)
        except Exception:
            pass
        # 2. 从绑定记录获取
        user_key = self._user_key(event)
        qq = self.user_store.get_qq(user_key)
        if qq and qq.isdigit():
            return int(qq)
        return None

    def _require_qq(self, event: AstrMessageEvent) -> int | None:
        """获取 QQ 号，未绑定则提示并返回 None。"""
        qq = self._get_qq(event)
        if qq is None:
            return None
        return qq

    # ================================================================
    # 帮助
    # ================================================================

    @command("help", alias={"帮助"})
    async def _help(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in help_handler(event):
            yield r

    # ================================================================
    # 群功能开关
    # ================================================================

    @command("maitoggle", alias={"开启舞萌功能", "关闭舞萌功能"})
    async def _toggle_maimai(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        text = event.get_message_str().strip()
        enable = "开启" in text
        group_id = self._group_id(event)
        if not group_id:
            yield self._message("此命令只能在群聊中使用。")
            return
        await self.group_store.toggle_group(group_id, enable)
        status = "开启" if enable else "关闭"
        yield self._message(f"✅ 群功能已{status}。")

    # ================================================================
    # 更新数据
    # ================================================================

    @command("maiupdate", alias={"更新maimai数据"})
    async def _update_data(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        try:
            await self.music_data.load_all()
            yield self._message(
                f"✅ 数据已更新：{len(self.music_data.music_list)} 首歌曲，"
                f"{len(self.music_data.alias_list)} 条别名"
            )
        except Exception as e:
            yield self._message(f"更新失败：{e}")

    # ================================================================
    # 统一查分路由
    # ================================================================

    async def _route_b50(self, event: AstrMessageEvent, game: str) -> None:
        """统一 B50/B30 路由。"""
        qq = self._require_qq(event)
        if qq is None:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `bindqq <你的QQ号>` 绑定。")
            return
        label = GAME_LABELS.get(game, game)
        table = self._table_name(game)

        # 发送"正在生成"提示，获取消息 ID 用于撤回
        gen_msg_id = await self._send_and_get_id(event, f"🎮 正在为 [{label}] 生成 {table}，请稍候...")

        # 生成并发送分表
        if game == "chunithm":
            async for r in chu_b30_handler(event, self.lxns, self.chu_data, qq=qq):
                yield r
        elif self._get_prober(event, "maimai") == "lxns":
            async for r in lxns_mai_b50_handler(event, self.lxns, qq=qq):
                yield r
        else:
            async for r in b50_handler(event, self.api, self.music_data, qq=qq):
                yield r

        # 撤回"正在生成"提示
        if gen_msg_id:
            await self._recall_msg(event, gen_msg_id)

    async def _send_and_get_id(self, event: AstrMessageEvent, text: str) -> str | None:
        """发送消息并返回消息 ID（用于后续撤回）。"""
        try:
            adapter = self.context.get_platform_inst(event.get_platform_id())
            if not adapter or not hasattr(adapter, "client"):
                return None
            client = adapter.client
            api = getattr(client, "api", None)
            if not api:
                return None
            group_id = self._group_id(event)

            if group_id:
                result = await api.post_group_message(
                    group_openid=group_id, msg_type=0, content=text,
                )
            else:
                result = await api.post_c2c_message(
                    openid=event.get_sender_id(), msg_type=0, content=text,
                )

            if result and hasattr(result, "id"):
                return str(result.id)
        except Exception as e:
            logger.warning(f"发送提示消息失败: {e}")
        return None

    async def _recall_msg(self, event: AstrMessageEvent, msg_id: str) -> None:
        """撤回 QQ 官方 API 消息（群聊 + 私聊）。"""
        try:
            adapter = self.context.get_platform_inst(event.get_platform_id())
            if not adapter or not hasattr(adapter, "client"):
                return
            client = adapter.client
            group_id = self._group_id(event)

            if group_id:
                url = f"/v2/groups/{group_id}/messages/{msg_id}"
            else:
                url = f"/v2/users/{event.get_sender_id()}/messages/{msg_id}"

            # 用 botpy 内部 HTTP 客户端发 DELETE 请求
            http = getattr(client, "_http", None) or getattr(client, "http", None)
            if http and hasattr(http, "request"):
                await http.request("DELETE", url)
            else:
                # fallback: 直接用 aiohttp
                import httpx
                async with httpx.AsyncClient(timeout=10) as hc:
                    await hc.delete(f"https://api.sgroup.qq.com{url}")
        except Exception as e:
            logger.warning(f"消息撤回失败: {e}")

    async def _route_minfo(self, event: AstrMessageEvent, game: str) -> None:
        """统一 minfo 路由。"""
        qq = self._require_qq(event)
        if qq is None:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `bindqq <你的QQ号>` 绑定。")
            return
        label = GAME_LABELS.get(game, game)
        yield self._message(f"🎮 正在为 [{label}] 查询歌曲成绩，请稍候...")
        if game == "chunithm":
            async for r in chu_minfo_handler(event, self.lxns, self.chu_data, qq=qq):
                yield r
        elif self._get_prober(event, "maimai") == "lxns":
            async for r in lxns_mai_minfo_handler(event, self.lxns, qq=qq):
                yield r
        else:
            async for r in minfo_handler(event, self.api, self.music_data, qq=qq):
                yield r

    # ================================================================
    # maimai 专属命令
    # ================================================================

    @command("maib50")
    async def _mai_b50(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in self._route_b50(event, "maimai"):
            yield r

    @command("maiminfo")
    async def _mai_minfo(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in self._route_minfo(event, "maimai"):
            yield r

    @command("maiginfo")
    async def _mai_ginfo(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        qq = self._get_qq(event)
        async for r in ginfo_handler(event, self.api, self.music_data, qq=qq):
            yield r

    @command("mailine")
    async def _mai_scoreline(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in score_line_handler(event, self.music_data):
            yield r

    # ================================================================
    # CHUNITHM 专属命令
    # ================================================================

    @command("b30", alias={"chub30"})
    async def _chu_b30(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in self._route_b50(event, "chunithm"):
            yield r

    @command("chuminfo")
    async def _chu_minfo(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in self._route_minfo(event, "chunithm"):
            yield r

    @command("chusearch")
    async def _chu_search(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in chu_search_handler(event, self.chu_data):
            yield r

    @command("chuid")
    async def _chu_id(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in chu_id_handler(event, self.chu_data):
            yield r

    # ================================================================
    # 无前缀命令 — 检测游戏模式后路由，并输出提示
    # ================================================================

    @command("b50")
    async def _b50(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        async for r in self._route_b50(event, game):
            yield r

    @command("minfo")
    async def _minfo(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        async for r in self._route_minfo(event, game):
            yield r

    @command("ginfo")
    async def _ginfo(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "chunithm":
            yield self._message("CHUNITHM 暂不支持 ginfo。")
        else:
            qq = self._get_qq(event)
            async for r in ginfo_handler(event, self.api, self.music_data, qq=qq):
                yield r

    @command("分数线")
    async def _scoreline(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "chunithm":
            yield self._message("CHUNITHM 暂不支持分数线。")
        else:
            async for r in score_line_handler(event, self.music_data):
                yield r

    @command("查歌")
    async def _search(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "chunithm":
            async for r in chu_search_handler(event, self.chu_data):
                yield r
        else:
            async for r in search_music_handler(event, self.music_data):
                yield r

    @command("id")
    async def _query_id(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "chunithm":
            async for r in chu_id_handler(event, self.chu_data):
                yield r
        else:
            async for r in query_by_id_handler(event, self.music_data):
                yield r

    # --- 排名（共用命令，根据游戏模式路由） ---

    @command("ranking", alias={"查看排名", "查看排行"})
    async def _ranking(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in ranking_handler(event, self.api):
                yield r
        else:
            yield self._message("CHUNITHM 暂无全局排行榜，请使用 `chub30` 查看个人 Rating 构成。")

    @command("myranking", alias={"我的排名"})
    async def _my_ranking(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        qq = self._require_qq(event)
        if qq is None:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `bindqq <你的QQ号>` 绑定。")
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in my_ranking_handler(event, self.api, qq=qq):
                yield r
        else:
            yield self._message("CHUNITHM 暂无全局排行榜，请使用 `chub30` 查看个人 Rating 构成。")

    # --- 搜索（mai 前缀直接执行，无前缀走游戏模式） ---

    @command("maisearch")
    async def _mai_search(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in search_music_handler(event, self.music_data):
            yield r

    @command("maibase")
    async def _mai_base(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in search_base_handler(event, self.music_data):
            yield r

    @command("maibpm")
    async def _mai_bpm(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in search_bpm_handler(event, self.music_data):
            yield r

    @command("maiartist")
    async def _mai_artist(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in search_artist_handler(event, self.music_data):
            yield r

    @command("maicharter")
    async def _mai_charter(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in search_charter_handler(event, self.music_data):
            yield r

    @command("maiid")
    async def _mai_id(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in query_by_id_handler(event, self.music_data):
            yield r

    # --- 猜歌（mai 前缀直接执行） ---

    @command("maiguess")
    async def _mai_guess(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        gid = self._group_id(event)
        if gid and not self.group_store.is_guess_enabled(gid):
            return
        async for r in guess_music_handler(event, self.music_data):
            yield r

    @command("maiguesspic")
    async def _mai_guess_pic(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        gid = self._group_id(event)
        if gid and not self.group_store.is_guess_enabled(gid):
            return
        async for r in guess_pic_handler(event, self.music_data):
            yield r

    @command("maiguessreset")
    async def _mai_guess_reset(self, event: AstrMessageEvent):
        async for r in reset_guess_handler(event, self.music_data):
            yield r

    @command("maiguesstoggle")
    async def _mai_guess_toggle(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        text = event.get_message_str().strip()
        enable = "开启" in text
        group_id = self._group_id(event)
        if not group_id:
            yield self._message("此命令只能在群聊中使用。")
            return
        await self.group_store.toggle_guess(group_id, enable)
        status = "开启" if enable else "关闭"
        yield self._message(f"✅ 群猜歌功能已{status}。")

    # --- 牌桌（mai 前缀直接执行） ---

    @command("maitable")
    async def _mai_table(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in rating_table_handler(event, self.music_data):
            yield r

    @command("mairise")
    async def _mai_rise(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in rise_score_handler(event, self.api, self.music_data):
            yield r

    # ================================================================
    # 共用命令 — 别名（不加 mai 前缀，根据游戏模式路由）
    # ================================================================

    @command("aliasupdate", alias={"更新别名库"})
    async def _update_alias(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in update_alias_handler(event, self.music_data):
                yield r
        else:
            yield self._message("CHUNITHM 别名功能暂未实现。")

    @command("aliasadd", alias={"添加别名", "增加别名", "增添别名", "添加别称"})
    async def _add_alias(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in alias_apply_handler(
                event, self.api, self.music_data,
                uuid=self.config.get("alias_push_uuid", ""),
            ):
                yield r
        else:
            yield self._message("CHUNITHM 别名功能暂未实现。")

    @command("aliaslocal", alias={"添加本地别名", "添加本地别称"})
    async def _add_local_alias(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in alias_local_apply_handler(event, self.music_data):
                yield r
        else:
            yield self._message("CHUNITHM 别名功能暂未实现。")

    @command("aliasvote", alias={"同意别名", "同意别称"})
    async def _agree_alias(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in alias_agree_handler(event, self.api):
                yield r
        else:
            yield self._message("CHUNITHM 别名功能暂未实现。")

    @command("aliasstatus", alias={"当前投票", "当前别名投票", "当前别称投票"})
    async def _alias_status(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in alias_status_handler(event, self.api):
                yield r
        else:
            yield self._message("CHUNITHM 别名功能暂未实现。")

    @command("aliastoggle", alias={"开启别名推送", "关闭别名推送"})
    async def _toggle_alias_push(self, event: AstrMessageEvent):
        async for r in alias_push_handler(event, self.group_store):
            yield r

    # ================================================================
    # 共用命令 — 机厅（不区分游戏）
    # ================================================================

    @command("arcadeadd", alias={"添加机厅", "新增机厅"})
    async def _add_arcade(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        async for r in add_arcade_handler(event, self.arcade_data):
            yield r

    @command("arcadedel", alias={"删除机厅", "移除机厅"})
    async def _delete_arcade(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        async for r in delete_arcade_handler(event, self.arcade_data):
            yield r

    @command("arcadeedit", alias={"修改机厅", "编辑机厅"})
    async def _modify_arcade(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        async for r in modify_arcade_handler(event, self.arcade_data):
            yield r

    @command("arcadealias", alias={"添加机厅别名", "删除机厅别名"})
    async def _arcade_alias(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        async for r in arcade_alias_handler(event, self.arcade_data):
            yield r

    @command("arcadesearch", alias={"查找机厅", "查询机厅", "机厅查找", "机厅查询"})
    async def _search_arcade(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in search_arcade_handler(event, self.arcade_data):
            yield r

    @command("arcadesub", alias={"订阅机厅", "取消订阅机厅", "取消订阅"})
    async def _subscribe_arcade(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in subscribe_handler(event, self.arcade_data):
            yield r

    @command("arcadestatus", alias={"查看订阅", "查看订阅机厅"})
    async def _check_sub(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in check_subscribe_handler(event, self.arcade_data):
            yield r

    # ================================================================
    # 正则匹配（不需要唤醒前缀）
    # ================================================================

    @event_message_type(EventMessageType.ALL)
    async def _on_message(self, event: AstrMessageEvent):
        """全局消息处理：猜歌答案、别名查歌、分数计算、运势等。"""
        if self._is_group_disabled(event):
            return

        text = event.get_message_str().strip()
        game = self._resolve_game(event)

        # --- 以下仅 maimai 模式 ---

        if game == "maimai":
            # 猜歌答案
            if is_group_message(event):
                async for r in guess_solve_handler(event, self.music_data):
                    yield r
                    return

            # 别名查歌：xxx是什么歌
            if re.search(r"(是什么歌|是啥歌)$", text):
                async for r in search_alias_handler(event, self.music_data):
                    yield r
                    return

            # 分数计算：X的Y是多少分
            if re.match(r"^[\d.]+的[\d.]+是多少分$", text):
                async for r in score_calc_handler(event, self.music_data):
                    yield r
                    return

            # 今日运势
            if re.match(r"^(今日mai|今日舞萌|今日运势)$", text):
                async for r in self._daily_fortune(event):
                    yield r
                    return

            # mai什么 / 随机歌曲
            if re.match(r"^.*mai.*什么", text):
                async for r in self._mai_what(event):
                    yield r
                    return

            # 来/随/给个 + 难度
            if re.match(r"^[来随给]个", text):
                async for r in self._random_song(event):
                    yield r
                    return

            # 分数线
            if text.startswith("分数线"):
                async for r in score_line_handler(event, self.music_data):
                    yield r
                    return

            # X定数表
            if re.match(r"^(?!更新).+?定数表$", text):
                async for r in rating_table_handler(event, self.music_data):
                    yield r
                    return

            # 版牌进度
            if re.search(r"进度\s*$", text):
                async for r in plate_progress_handler(event, self.api, self.music_data):
                    yield r
                    return
                async for r in level_progress_handler(event, self.api, self.music_data):
                    yield r
                    return

            # 推分
            if re.match(r"^我要在", text):
                async for r in rise_score_handler(event, self.api, self.music_data):
                    yield r
                    return

            # 查询别名
            if re.search(r"有什么别[名称]$", text):
                async for r in alias_query_handler(event, self.music_data):
                    yield r
                    return

        # --- 以下仅 chunithm 模式 ---

        if game == "chunithm":
            # TODO: chunithm 正则命令
            pass

        # --- 共用：机厅（不区分游戏） ---

        # 机厅排队查询
        if re.match(r"^(机厅几人|jtj|.+有几人|.+有几卡|.+几人|.+几卡|jr)$", text, re.I):
            async for r in arcade_query_handler(event, self.arcade_data):
                yield r
                return

        # 机厅人数设置
        if re.match(r"^.+\s?(设置|设定|加|减|\+|-)\s?\d+(人|卡)?$", text):
            async for r in arcade_person_handler(event, self.arcade_data):
                yield r
                return

    # ================================================================
    # 内置功能
    # ================================================================

    async def _daily_fortune(self, event: AstrMessageEvent):
        """每日运势。"""
        from .utils import qq_hash, now_cn, secure_choice

        qq = event.get_sender_id()
        today = now_cn().strftime("%Y%m%d")
        seed = int(f"{qq_hash(qq)}{today}")
        import random
        rng = random.Random(seed)

        music = (
            secure_choice(list(self.music_data.music_list))
            if self.music_data.music_list else None
        )

        fortunes = [
            ("大吉", "今天打 mai 一定会有好成绩！"),
            ("中吉", "稳扎稳打，今天适合刷分。"),
            ("小吉", "小心手滑，注意节奏。"),
            ("吉", "平平淡淡才是真。"),
            ("末吉", "今天可能不太顺利，休息一下吧。"),
        ]
        fortune = rng.choice(fortunes)

        lines = [f"🎱 今日运势 — {fortune[0]}", fortune[1]]
        if music:
            lines.append(f"🎵 今日推荐：{music.title}")

        yield self._message("\n".join(lines))

    async def _mai_what(self, event: AstrMessageEvent):
        """mai什么 — 随机推荐。"""
        from .utils import secure_choice

        music = (
            secure_choice(list(self.music_data.music_list))
            if self.music_data.music_list else None
        )
        if not music:
            yield self._message("曲库为空。")
            return

        levels = " / ".join(music.level)
        yield self._message(
            f"🎵 随机推荐：{music.title}\n"
            f"  曲师: {music.basic_info.artist}\n"
            f"  难度: {levels}\n"
            f"  BPM: {music.basic_info.bpm}"
        )

    async def _random_song(self, event: AstrMessageEvent):
        """来/随/给个 + 难度等级。"""
        text = event.get_message_str().strip()
        m = re.match(r"^[来随给]个(?:(dx|sd|标准))?([绿黄红紫白]?)([0-9]+\+?)$", text)
        if not m:
            return

        type_filter = m.group(1)
        diff_char = m.group(2)
        level = m.group(3)

        type_map = {"dx": "DX", "sd": "SD", "标准": "SD"}
        music_type = type_map.get(type_filter) if type_filter else None

        from .music_data import diff_label_to_index
        diff_idx = diff_label_to_index.get(diff_char)

        music = self.music_data.random_music(level=level, diff=diff_idx, type=music_type)
        if not music:
            yield self._message("未找到符合条件的歌曲。")
            return

        levels = " / ".join(music.level)
        yield self._message(
            f"🎵 随机选歌：{music.title}\n"
            f"  类型: {music.type} | 难度: {levels}"
        )
