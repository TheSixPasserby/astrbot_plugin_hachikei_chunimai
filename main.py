"""插件入口：注册、命令路由、生命周期管理。"""

from __future__ import annotations

import asyncio
import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.all import register
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.event.filter import EventMessageType, command, event_message_type
from astrbot.api.star import Context, Star, StarTools

from .api_client import MaimaiAPI
from .lxns_client import LxnsAPI
from .chu_data import ChuDataManager
from .command.chunithm import chu_b30_handler, chu_minfo_handler, chu_search_handler, chu_id_handler, chu_alias_query_handler
from .command.mai_score import lxns_mai_b50_handler, lxns_mai_minfo_handler
from .command.alias import (
    AliasPushService, alias_agree_handler, alias_apply_handler,
    alias_global_push_handler, alias_local_apply_handler, alias_push_handler,
    alias_query_handler, alias_status_handler, update_alias_handler,
)
from .command.mai_guess import (
    mai_guess_music_handler, mai_guess_pic_handler, mai_guess_solve_handler,
    mai_reset_guess_handler,
)
from .command.help import help_handler
from .command.mai_score import (
    mai_b50_handler, mai_ginfo_handler, mai_minfo_handler, mai_my_ranking_handler,
    mai_ranking_handler, mai_score_calc_handler, mai_score_line_handler,
)
from .command.mai_search import (
    mai_query_by_id_handler, mai_search_alias_handler, mai_search_artist_handler,
    mai_search_base_handler, mai_search_bpm_handler, mai_search_charter_handler,
    mai_search_music_handler,
)
from .command.mai_table import (
    mai_level_achievement_list_handler, mai_level_progress_handler,
    mai_plate_progress_handler, mai_rating_table_handler, mai_rise_score_handler,
)
from .errors import MaimaiError, describe_error
from .mai_data import MusicDataManager
from .storage import GroupConfigStore, UserStore
from .utils import get_platform_adapter_name, is_group_message

VALID_GAMES = {"maimai", "chunithm"}
GAME_LABELS = {"maimai": "maimai DX", "chunithm": "CHUNITHM"}


@register(
    "astrbot_plugin_hachikei_chunimai",
    "TheSixPasserby",
    "maimai DX / CHUNITHM 综合助手：查分、搜歌、猜歌、牌桌、别名。",
    "0.1.0",
    "",
)
class MaiChuPlugin(Star):
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
        token = self.config.get("mai_divingfish_token", "")
        proxy = bool(self.config.get("http_proxy", ""))
        self.api.configure(token=token, proxy=proxy)

        # Lxns
        lxns_key = self.config.get("lxns_dev_key", "")
        lxns_token = self.config.get("lxns_user_token", "")
        self.lxns.configure(dev_key=lxns_key, user_token=lxns_token)

        # 配置舞萌别名数据源
        mai_alias_src = self.config.get("mai_alias_source", "yuzuchan")
        self.music_data.configure_alias(source=mai_alias_src, lxns=self.lxns)

        try:
            await self.music_data.load_all()
        except Exception as e:
            logger.error(f"加载歌曲数据失败: {e}")

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

    @command("bindtoken", alias={"绑定token", "绑定落雪"})
    async def _bind_token(self, event: AstrMessageEvent):
        """落雪 OAuth 绑定。用法：bindtoken 或 bindtoken <code>"""
        args = event.get_message_str().strip().split(maxsplit=1)
        client_id = self.config.get("lxns_client_id", "")
        client_secret = self.config.get("lxns_client_secret", "")

        # 没有 OAuth 配置
        if not client_id or not client_secret:
            yield self._message(
                "⚠️ 管理员未配置落雪 OAuth 应用。\n"
                "请在插件配置中填写 `lxns_client_id` 和 `lxns_client_secret`。\n"
                "或手动在 maimai.lxns.net/user/profile 获取 Token 后配置 `lxns_user_token`。"
            )
            return

        # bindtoken（无参数）— 生成授权链接
        if len(args) < 2:
            redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            oauth_url = (
                f"https://maimai.lxns.net/oauth/authorize"
                f"?response_type=code"
                f"&client_id={client_id}"
                f"&redirect_uri={redirect_uri}"
                f"&scope=read_user_profile+read_player+write_player"
            )
            yield self._message(
                f"🔗 请点击链接授权落雪查分器：\n{oauth_url}\n\n"
                f"授权后页面会显示一串 code，请复制并发送：\n"
                f"bindtoken <code>"
            )
            return

        # bindtoken <code> — 交换 access_token
        code = args[1].strip()
        redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        try:
            access_token = await self.lxns.oauth_exchange(code, client_id, client_secret, redirect_uri)
        except Exception as e:
            yield self._message(f"❌ 授权失败：{e}")
            return

        user_key = self._user_key(event)
        await self.user_store.set_lxns_token(user_key, access_token)
        yield self._message("✅ 落雪查分器绑定成功！现在可以直接使用 minfo、b50 等命令查分。")

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

    def _get_lxns_token(self, event: AstrMessageEvent) -> str:
        """获取用户的有效落雪 token：优先 OAuth 绑定，其次全局配置。"""
        user_key = self._user_key(event)
        token = self.user_store.get_lxns_token(user_key)
        if token:
            return token
        return self.config.get("lxns_user_token", "")

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

    @command("gametoggle", alias={"开启功能", "关闭功能", "maitoggle"})
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
    # 别名数据源切换
    # ================================================================

    @command("switchalias", alias={"更改别名源", "切换别名源"})
    async def _switch_alias_source(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            yield self._message("需要管理员权限。")
            return
        text = event.get_message_str().strip()
        # 解析: 更改别名源 舞萌/中二 水鱼/落雪
        import re
        m = re.search(r"(舞萌|maimai|中二|chunithm)\s*(水鱼|yuzuchan|落雪|lxns)", text, re.IGNORECASE)
        if not m:
            yield self._message(
                "用法：更改别名源 <游戏> <数据源>\n"
                "游戏：舞萌 / 中二\n"
                "数据源：水鱼 / 落雪\n"
                "例如：更改别名源 舞萌 落雪"
            )
            return

        game_raw = m.group(1).lower()
        source_raw = m.group(2).lower()

        game = "maimai" if game_raw in ("舞萌", "maimai") else "chunithm"
        source = "lxns" if source_raw in ("落雪", "lxns") else "yuzuchan"

        if game == "chunithm" and source == "yuzuchan":
            yield self._message("中二节奏暂不支持柚子别名源，请使用落雪。")
            return

        # 保存配置
        key = "mai_alias_source" if game == "maimai" else "chu_alias_source"
        self.config[key] = source
        try:
            self.context.save_config()
        except Exception:
            pass

        # 重新加载别名
        label = "舞萌" if game == "maimai" else "中二"
        src_label = "落雪" if source == "lxns" else "柚子"
        yield self._message(f"🔄 正在从{src_label}重新加载{label}别名数据...")

        if game == "maimai":
            self.music_data.configure_alias(source=source, lxns=self.lxns)
            try:
                await self.music_data.load_alias_data()
                yield self._message(f"✅ {label}别名源已切换为 {src_label}，共 {len(self.music_data.alias_list)} 条。")
            except Exception as e:
                yield self._message(f"❌ 加载别名失败：{e}")
        else:
            try:
                await self.chu_data.load_aliases()
                yield self._message(f"✅ {label}别名源已切换为 {src_label}，共 {len(self.chu_data.aliases)} 条。")
            except Exception as e:
                yield self._message(f"❌ 加载别名失败：{e}")

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
        # 临时设置用户 token（OAuth > 全局配置）
        user_token = self._get_lxns_token(event)
        saved_token = self.lxns._user_token
        if user_token:
            self.lxns._user_token = user_token
        qq = self._get_qq(event)
        if qq is None and not user_token:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `bindqq <你的QQ号>` 或 `bindtoken` 绑定。")
            return
        try:
            if game == "chunithm":
                async for r in chu_b30_handler(event, self.lxns, self.chu_data, qq=qq):
                    yield r
            elif self._get_prober(event, "maimai") == "lxns":
                async for r in lxns_mai_b50_handler(event, self.lxns, qq=qq, music_data=self.music_data):
                    yield r
            else:
                async for r in mai_b50_handler(event, self.api, self.music_data, qq=qq):
                    yield r
        finally:
            self.lxns._user_token = saved_token

    async def _route_minfo(self, event: AstrMessageEvent, game: str) -> None:
        """统一 minfo 路由。"""
        user_token = self._get_lxns_token(event)
        saved_token = self.lxns._user_token
        if user_token:
            self.lxns._user_token = user_token
        qq = self._get_qq(event)
        if qq is None and not user_token:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `bindqq <你的QQ号>` 或 `bindtoken` 绑定。")
            return
        try:
            if game == "chunithm":
                async for r in chu_minfo_handler(event, self.lxns, self.chu_data, qq=qq):
                    yield r
            elif self._get_prober(event, "maimai") == "lxns":
                async for r in lxns_mai_minfo_handler(event, self.lxns, qq=qq, music_data=self.music_data):
                    yield r
            else:
                async for r in mai_minfo_handler(event, self.api, self.music_data, qq=qq):
                    yield r
        finally:
            self.lxns._user_token = saved_token

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
        async for r in mai_ginfo_handler(event, self.api, self.music_data, qq=qq):
            yield r

    @command("mailine")
    async def _mai_scoreline(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_score_line_handler(event, self.music_data):
            yield r

    # ================================================================
    # CHUNITHM 专属命令
    # ================================================================

    @command("chub30", alias={"b30"})
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
            async for r in mai_ginfo_handler(event, self.api, self.music_data, qq=qq):
                yield r

    @command("分数线")
    async def _scoreline(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "chunithm":
            yield self._message("CHUNITHM 暂不支持分数线。")
        else:
            async for r in mai_score_line_handler(event, self.music_data):
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
            async for r in mai_search_music_handler(event, self.music_data):
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
            async for r in mai_query_by_id_handler(event, self.music_data):
                yield r

    # --- 排名（共用命令，根据游戏模式路由） ---

    @command("ranking", alias={"查看排名", "查看排行"})
    async def _ranking(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "maimai":
            async for r in mai_ranking_handler(event, self.api):
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
            async for r in mai_my_ranking_handler(event, self.api, qq=qq):
                yield r
        else:
            yield self._message("CHUNITHM 暂无全局排行榜，请使用 `chub30` 查看个人 Rating 构成。")

    # --- 搜索（mai 前缀直接执行，无前缀走游戏模式） ---

    @command("maisearch")
    async def _mai_search(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_search_music_handler(event, self.music_data):
            yield r

    @command("maibase")
    async def _mai_base(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_search_base_handler(event, self.music_data):
            yield r

    @command("maibpm")
    async def _mai_bpm(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_search_bpm_handler(event, self.music_data):
            yield r

    @command("maiartist")
    async def _mai_artist(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_search_artist_handler(event, self.music_data):
            yield r

    @command("maicharter")
    async def _mai_charter(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_search_charter_handler(event, self.music_data):
            yield r

    @command("maiid")
    async def _mai_id(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_query_by_id_handler(event, self.music_data):
            yield r

    # --- 猜歌（mai 前缀直接执行） ---

    @command("maiguess")
    async def _mai_guess(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        gid = self._group_id(event)
        if gid and not self.group_store.is_guess_enabled(gid):
            return
        async for r in mai_guess_music_handler(event, self.music_data):
            yield r

    @command("maiguesspic")
    async def _mai_guess_pic(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        gid = self._group_id(event)
        if gid and not self.group_store.is_guess_enabled(gid):
            return
        async for r in mai_guess_pic_handler(event, self.music_data):
            yield r

    @command("maiguessreset")
    async def _mai_guess_reset(self, event: AstrMessageEvent):
        async for r in mai_reset_guess_handler(event, self.music_data):
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
        async for r in mai_rating_table_handler(event, self.music_data):
            yield r

    @command("mairise")
    async def _mai_rise(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        async for r in mai_rise_score_handler(event, self.api, self.music_data):
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
                async for r in mai_guess_solve_handler(event, self.music_data):
                    yield r
                    return

            # 别名查歌：xxx是什么歌
            if re.search(r"(是什么歌|是啥歌)$", text):
                async for r in mai_search_alias_handler(event, self.music_data):
                    yield r
                    return

            # 分数计算：X的Y是多少分
            if re.match(r"^[\d.]+的[\d.]+是多少分$", text):
                async for r in mai_score_calc_handler(event, self.music_data):
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
                async for r in mai_score_line_handler(event, self.music_data):
                    yield r
                    return

            # X定数表
            if re.match(r"^(?!更新).+?定数表$", text):
                async for r in mai_rating_table_handler(event, self.music_data):
                    yield r
                    return

            # 版牌进度 / 等级进度
            if re.search(r"进度\s*$", text):
                async for r in mai_plate_progress_handler(event, self.api, self.music_data):
                    yield r
                return

            # 推分
            if re.match(r"^我要在", text):
                async for r in mai_rise_score_handler(event, self.api, self.music_data):
                    yield r
                    return

        # --- 共用：别名查询（按游戏路由） ---

        if re.search(r"有什么别[名称]$", text):
            if game == "chunithm":
                async for r in chu_alias_query_handler(event, self.chu_data):
                    yield r
            else:
                async for r in alias_query_handler(event, self.music_data):
                    yield r
            return

        # --- 以下仅 chunithm 模式 ---

        if game == "chunithm":
            # TODO: chunithm 正则命令
            pass

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

        from .mai_data import DIFF_LABEL_TO_INDEX
        diff_idx = DIFF_LABEL_TO_INDEX.get(diff_char)

        music = self.music_data.random_music(level=level, diff=diff_idx, type=music_type)
        if not music:
            yield self._message("未找到符合条件的歌曲。")
            return

        levels = " / ".join(music.level)
        yield self._message(
            f"🎵 随机选歌：{music.title}\n"
            f"  类型: {music.type} | 难度: {levels}"
        )
