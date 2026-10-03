"""插件入口：注册、命令路由、生命周期管理。"""

from __future__ import annotations

import asyncio
import re
import time

from astrbot.api import AstrBotConfig, logger
from astrbot.api.all import register
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.event.filter import EventMessageType, command, event_message_type
from astrbot.api.star import Context, Star, StarTools

from .api_client import MaimaiAPI
from .lxns_client import LxnsAPI
from .chu_data import ChuDataManager
from .command.chu_score import chu_b30_handler, chu_minfo_handler, chu_search_handler, chu_id_handler, chu_alias_query_handler, chu_search_alias_handler
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
from .command.help import help_handler, admin_help_handler
from .command.fun import daily_fortune_handler, mai_what_handler, random_song_handler
from .command.account import AccountService
from .command.admin import AdminService
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
from .mai_data import MusicDataManager
from .storage import GroupConfigStore, UserStore
from .utils import is_group_message



@register(
    "astrbot_plugin_hachikei_chunimai",
    "TheSixPasserby",
    "maimai DX / CHUNITHM 综合助手：查分、搜歌、猜歌、牌桌、别名。",
    "0.2.8",
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
        self.http_proxy: str = self.config.get("http_proxy", "") or ""

        # 子系统
        self.api = MaimaiAPI(timeout=self.timeout, http_proxy=self.http_proxy)
        self.lxns = LxnsAPI(timeout=self.timeout, http_proxy=self.http_proxy)
        self.user_store = UserStore(data_dir)
        self.group_store = GroupConfigStore(data_dir)
        self.music_data = MusicDataManager(self.api, data_dir)
        self.chu_data = ChuDataManager(self.lxns, data_dir)
        self.music_data_ready = False
        self.chu_data_ready = False
        self.alias_push = AliasPushService(self.api, self.config.get("alias_push_uuid", ""))
        self._qr_sync = None  # QRSyncService，延迟初始化（需要 maimai-py）

        # 账号绑定服务（封装 OAuth / 水鱼 Token 等待状态）
        self.account = AccountService(self.user_store, self.group_store, self.config, self.lxns)
        self.admin = AdminService(
            user_store=self.user_store,
            group_store=self.group_store,
            config=self.config,
            context=context,
            music_data=self.music_data,
            chu_data=self.chu_data,
            get_qr_sync=lambda: self._qr_sync,
            is_admin=self._is_admin,
            group_id_of=self._group_id,
            user_key_of=self._user_key,
            message=lambda event, text: MessageEventResult().message(text),
        )
        # 同步数据等待状态: {user_key: (prober, expire_timestamp)}
        self._pending_sync: dict[str, tuple[str, float]] = {}

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
        use_yuzuchan_proxy = bool(self.config.get("use_yuzuchan_proxy", False))
        self.api.configure(token=token, use_proxy=use_yuzuchan_proxy)

        # Lxns
        lxns_key = self.config.get("lxns_dev_key", "")
        self.lxns.configure(dev_key=lxns_key)

        # 配置舞萌别名数据源
        mai_alias_src = self.config.get("mai_alias_source", "yuzuchan")
        self.music_data.configure_alias(source=mai_alias_src, lxns=self.lxns)

        try:
            await self.music_data.load_all()
            self.music_data_ready = True
        except Exception as e:
            logger.error(f"加载歌曲数据失败: {e}")

        try:
            await self.chu_data.load_all()
            self.chu_data_ready = True
        except Exception as e:
            logger.error(f"加载 CHUNITHM 数据失败: {e}")

        # 启动别名推送
        if self.config.get("enable_alias_push") and self.config.get("alias_push_uuid"):
            await self.alias_push.start(self.context, self.group_store)

        # 初始化二维码同步服务
        try:
            from .qr_sync import QRSyncService
            proxy = self.http_proxy
            df_dev_token = self.config.get("mai_divingfish_token", "")
            self._qr_sync = QRSyncService(timeout=self.timeout, proxy=proxy, df_dev_token=df_dev_token)
            logger.info("QR 同步服务已初始化（maimai-py）")
        except Exception as e:
            logger.warning(f"QR 同步服务初始化失败（maimai-py 未安装？）: {e}")

        # 验证已绑定的落雪 token
        await self._validate_lxns_tokens()

        logger.info("maimai DX / CHUNITHM 插件已加载")

    async def _validate_lxns_tokens(self) -> None:
        """插件重载时验证所有已绑定的落雪 token，尝试刷新后验证，仅 401 明确失效时清除。"""
        all_tokens = self.user_store.get_all_lxns_tokens()
        if not all_tokens:
            return
        logger.info(f"正在验证 {len(all_tokens)} 个落雪 token...")
        client_id = self.config.get("lxns_client_id", "")
        client_secret = self.config.get("lxns_client_secret", "")
        expired = []
        for user_key, token in all_tokens.items():
            # access_token 15 分钟过期，先用 refresh_token 刷新
            refresh_token = self.user_store.get_lxns_refresh_token(user_key)
            if refresh_token and client_id and client_secret:
                try:
                    new_token, new_refresh = await self.lxns.oauth_refresh(
                        refresh_token, client_id, client_secret
                    )
                    await self.user_store.set_lxns_token(
                        user_key, new_token, new_refresh, expires_at=time.time() + 15 * 60
                    )
                    token = new_token
                    logger.debug(f"落雪 token 已刷新 ({user_key})")
                except Exception as e:
                    logger.debug(f"落雪 token 刷新失败，尝试旧 token ({user_key}): {e}")

            # 验证 token
            try:
                await self.lxns.oauth_get_player(token, "maimai")
            except Exception as e:
                err_str = str(e).lower()
                if "401" in err_str or "unauthorized" in err_str or "invalid" in err_str:
                    expired.append(user_key)
                    await self.user_store.remove_lxns_token(user_key)
                    logger.warning(f"落雪 token 失效 ({user_key}): {e}")
                else:
                    logger.debug(f"落雪 token 验证跳过（非认证错误）({user_key}): {e}")
        if expired:
            self.account._expired_tokens = set(expired)
            logger.warning(f"落雪 token 失效 {len(expired)} 个，已自动清除")
        else:
            logger.info("所有落雪 token 验证通过")

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
        """解析当前用户的查询游戏。优先级：个人设置 > 群默认 > maimai"""
        user_key = self._user_key(event)
        personal = self.user_store.get_game_mode(user_key)
        if personal:
            return personal
        gid = self._group_id(event)
        if gid:
            return self.group_store.get_group_game_mode(gid)
        return "maimai"

    # ================================================================
    @command("更改游戏", alias={"game", "切换游戏"})
    async def _switch_game(self, event: AstrMessageEvent):
        async for r in self.admin.switch_game(event):
            yield r

    @command("switchprober", alias={"切换查分器", "更改查分器"})
    async def _switch_prober(self, event: AstrMessageEvent):
        async for r in self.admin.switch_prober(event):
            yield r

    def _get_prober(self, event: AstrMessageEvent, game: str) -> str:
        return self.admin.get_prober(event, game)

    # 绑定 QQ
    # ================================================================

    @command("绑定QQ")
    async def _bind_qq(self, event: AstrMessageEvent):
        async for r in self.account.bind_qq(event):
            yield r

    @command("bindlxns", alias={"绑定落雪"})
    async def _bind_lxns(self, event: AstrMessageEvent):
        async for r in self.account.bind_lxns(event):
            yield r

    @command("unbindlxns", alias={"解绑落雪"})
    async def _unbind_lxns(self, event: AstrMessageEvent):
        async for r in self.account.unbind_lxns(event):
            yield r

    @command("binddf", alias={"绑定水鱼"})
    async def _bind_divingfish(self, event: AstrMessageEvent):
        async for r in self.account.bind_divingfish(event):
            yield r

    @command("unbinddf", alias={"解绑水鱼"})
    async def _unbind_divingfish(self, event: AstrMessageEvent):
        async for r in self.account.unbind_divingfish(event):
            yield r

    @command("account", alias={"绑定账号", "账号状态", "我的绑定"})
    async def _account_status(self, event: AstrMessageEvent):
        async for r in self.account.account_status(event):
            yield r

    # 帮助
    # ================================================================

    @command("help", alias={"帮助"})
    async def _help(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        current_game = self._resolve_game(event)
        gid = self._group_id(event)
        group_game = self.group_store.get_group_game_mode(gid) if gid else None
        async for r in help_handler(event, current_game, group_game):
            yield r

    @command("ahelp", alias={"管理帮助"})
    async def _admin_help(self, event: AstrMessageEvent):
        if not self._is_admin(event):
            return
        async for r in admin_help_handler(event):
            yield r

    @command("插件状态")
    async def _plugin_status(self, event: AstrMessageEvent):
        async for r in self.admin.plugin_status(event):
            yield r

    @command("gametoggle", alias={"开启功能", "关闭功能", "maitoggle"})
    async def _toggle_maimai(self, event: AstrMessageEvent):
        async for r in self.admin.toggle_maimai(event):
            yield r

    @command("switchalias", alias={"更改别名源", "切换别名源"})
    async def _switch_alias_source(self, event: AstrMessageEvent):
        async for r in self.admin.switch_alias_source(event):
            yield r

    @command("maiupdate", alias={"更新maimai数据"})
    async def _update_data(self, event: AstrMessageEvent):
        async for r in self.admin.update_data(event):
            yield r

    # 统一查分路由
    # ================================================================

    def _music_ready(self) -> bool:
        return self.music_data_ready and len(self.music_data.music_list) > 0

    def _chu_ready(self) -> bool:
        return self.chu_data_ready and len(self.chu_data.songs) > 0

    async def _route_b50(self, event: AstrMessageEvent, game: str) -> None:
        """统一 B50/B30 路由。"""
        user_token = await self._get_lxns_token(event)
        saved_token = self.lxns._user_token
        if user_token:
            self.lxns._user_token = user_token
        qq = self._get_qq(event)
        prober = self._get_prober(event, "maimai") if game == "maimai" else "lxns"
        logger.info(f"[B50] game={game}, prober={prober}, qq={qq}, has_token={bool(user_token)}")
        if qq is None and not user_token:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `绑定QQ <你的QQ号>` 或 `绑定落雪` 绑定。")
            return
        if game == "chunithm" and not self._chu_ready():
            yield self._message("⚠️ CHUNITHM 曲库未就绪，请稍后重试或让管理员更新数据。")
            return
        if game == "maimai" and not self._music_ready():
            yield self._message("⚠️ maimai 曲库未就绪，请稍后重试或让管理员更新数据。")
            return
        try:
            if game == "chunithm":
                async for r in chu_b30_handler(event, self.lxns, self.chu_data, qq=qq):
                    yield r
            elif prober == "lxns":
                async for r in lxns_mai_b50_handler(event, self.lxns, qq=qq, music_data=self.music_data):
                    yield r
            else:
                async for r in mai_b50_handler(event, self.api, self.music_data, qq=qq):
                    yield r
        finally:
            self.lxns._user_token = saved_token

    async def _route_minfo(self, event: AstrMessageEvent, game: str) -> None:
        """统一 minfo 路由。"""
        user_token = await self._get_lxns_token(event)
        saved_token = self.lxns._user_token
        if user_token:
            self.lxns._user_token = user_token
        qq = self._get_qq(event)
        prober = self._get_prober(event, "maimai") if game == "maimai" else "lxns"
        logger.info(f"[minfo] game={game}, prober={prober}, qq={qq}, has_token={bool(user_token)}")
        if qq is None and not user_token:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `绑定QQ <你的QQ号>` 或 `绑定落雪` 绑定。")
            return
        if game == "chunithm" and not self._chu_ready():
            yield self._message("⚠️ CHUNITHM 曲库未就绪，请稍后重试或让管理员更新数据。")
            return
        if game == "maimai" and not self._music_ready():
            yield self._message("⚠️ maimai 曲库未就绪，请稍后重试或让管理员更新数据。")
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
        if not self._chu_ready():
            yield self._message("⚠️ CHUNITHM 曲库未就绪。")
            return
        async for r in chu_search_handler(event, self.chu_data):
            yield r

    @command("chuid")
    async def _chu_id(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        if not self._chu_ready():
            yield self._message("⚠️ CHUNITHM 曲库未就绪。")
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
            if not self._chu_ready():
                yield self._message("⚠️ CHUNITHM 曲库未就绪。")
                return
            async for r in chu_search_handler(event, self.chu_data):
                yield r
        else:
            if not self._music_ready():
                yield self._message("⚠️ maimai 曲库未就绪。")
                return
            async for r in mai_search_music_handler(event, self.music_data):
                yield r

    @command("id")
    async def _query_id(self, event: AstrMessageEvent):
        if self._is_group_disabled(event):
            return
        game = self._resolve_game(event)
        if game == "chunithm":
            if not self._chu_ready():
                yield self._message("⚠️ CHUNITHM 曲库未就绪。")
                return
            async for r in chu_id_handler(event, self.chu_data):
                yield r
        else:
            if not self._music_ready():
                yield self._message("⚠️ maimai 曲库未就绪。")
                return
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
        qq = self._get_qq(event)
        if qq is None:
            yield self._message("⚠️ 未绑定 QQ 号，请先执行 `绑定QQ <你的QQ号>` 绑定。")
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
        prober = self._get_prober(event, "maimai")
        lxns_token = await self._get_lxns_token(event)
        qq = self._get_qq(event)
        async for r in mai_rise_score_handler(event, self.api, self.music_data, prober=prober, lxns=self.lxns, lxns_token=lxns_token, qq=qq):
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
    # 同步数据（先发命令，再发二维码）
    # ================================================================

    @command("syncdata", alias={"同步数据"})
    async def _sync_data(self, event: AstrMessageEvent):
        """同步街机数据到查分器。用法：同步数据 水鱼/落雪"""
        args = event.get_message_str().strip().split(maxsplit=1)
        target = args[1].strip().lower() if len(args) > 1 else ""

        user_key = self._user_key(event)
        lxns_token = await self._get_lxns_token(event)
        df_token = self.user_store.get_divingfish_token(user_key)

        if target in ("水鱼", "divingfish", "df"):
            if not df_token:
                yield self._message("⚠️ 未绑定水鱼查分器，请先发送「绑定水鱼 <Token>」。")
                return
            prober = "divingfish"
            label = "水鱼"
        elif target in ("落雪", "lxns"):
            if not lxns_token:
                yield self._message("⚠️ 未绑定落雪查分器，请先发送「绑定落雪」。")
                return
            prober = "lxns"
            label = "落雪"
        else:
            yield self._message("用法：同步数据 水鱼/落雪")
            return

        self._pending_sync[user_key] = (prober, time.time() + 3 * 60)
        yield self._message(
            f"🔗 请在 **3 分钟内** 发送街机二维码（SGWCMAID...），将同步到{label}查分器。"
        )

        # 3 分钟超时提醒
        async def _timeout():
            await asyncio.sleep(3 * 60)
            if self._pending_sync.pop(user_key, None):
                try:
                    result = event.make_result().message("⏰ 同步超时，请重新发送「同步数据 水鱼/落雪」。")
                    await event.send(result)
                except Exception:
                    pass
        asyncio.create_task(_timeout())

    async def _try_sync_sgid(self, event: AstrMessageEvent, sgid: str):
        """等待中的同步：收到 SGID 后执行同步。"""
        from .qr_sync import extract_sgid, is_valid_sgid

        if not sgid:
            sgid = extract_sgid(event.get_message_str()) or ""
        if not sgid:
            return

        user_key = self._user_key(event)
        pending = self._pending_sync.get(user_key)
        if not pending or time.time() > pending[1]:
            self._pending_sync.pop(user_key, None)
            return

        # 只验证格式，不检查 SGID 新鲜度（可能在二维码上停留了几分钟）
        if not is_valid_sgid(sgid):
            logger.warning(f"[sync] SGID 格式无效: {sgid[:20]}...")
            return

        prober = pending[0]
        del self._pending_sync[user_key]

        lxns_token = await self._get_lxns_token(event)
        df_token = self.user_store.get_divingfish_token(user_key)
        label = "水鱼" if prober == "divingfish" else "落雪"
        logger.info(f"[sync] 开始同步: prober={prober}, user={user_key}")

        yield self._message(f"🎮 正在同步成绩到{label}，请稍候...")

        try:
            if prober == "lxns":
                result = await self._qr_sync.sync_to_lxns(sgid, lxns_token)
            else:
                result = await self._qr_sync.sync_to_divingfish(sgid, df_token)

            lines = [
                f"✅ 同步成功！",
                f"  玩家: {result.player_name}" if result.player_name else "",
                f"  Rating: {result.rating}",
                f"  同步曲数: {result.score_count}",
            ]
            if result.warning:
                lines.append(f"  ⚠️ {result.warning}")
            yield self._message("\n".join(lines))

        except Exception as e:
            err_msg = self._qr_sync.describe_error(e)
            logger.exception("同步数据失败")
            yield self._message(f"❌ {err_msg}")

    # ================================================================
    # 正则匹配（不需要唤醒前缀）
    # ================================================================

    @event_message_type(EventMessageType.ALL)
    async def _on_message(self, event: AstrMessageEvent):
        """全局消息处理：猜歌答案、别名查歌、分数计算、运势等。"""
        if self._is_group_disabled(event):
            return
        # 跳过机器人自身消息（避免 bot 回复触发监听）
        try:
            if event.get_sender_id() == event.get_self_id():
                return
        except AttributeError:
            pass

        # OAuth 密钥监听（5 分钟内直接发送密钥）
        if self.account._pending_oauth.get(self._user_key(event)):
            async for r in self.account.try_oauth_code(event):
                yield r
            return

        # 水鱼 Token 监听（5 分钟内直接发送 Token）
        if self.account._pending_df.get(self._user_key(event)):
            if await self.account.try_df_token(event):
                msg = self.account._pending_df_message
                if msg:
                    yield self._message(msg)
                    self.account._pending_df_message = None
                return

        text = event.get_message_str().strip()

        # 同步数据等待中的 SGWCMAID 检测
        if self._qr_sync and self._pending_sync.get(self._user_key(event)) and "SGWCMAID" in text.upper():
            from .qr_sync import extract_sgid
            sgid = extract_sgid(text)
            if sgid:
                async for r in self._try_sync_sgid(event, sgid):
                    yield r
                return

        game = self._resolve_game(event)

        # --- 以下仅 maimai 模式 ---

        if game == "maimai":
            # 猜歌答案
            if is_group_message(event):
                async for r in mai_guess_solve_handler(event, self.music_data):
                    yield r
                return

            # 分数计算：X的Y是多少分
            if re.match(r"^[\d.]+的[\d.]+是多少分$", text):
                async for r in mai_score_calc_handler(event, self.music_data):
                    yield r
                    return

            # 今日运势
            if re.match(r"^(今日mai|今日舞萌|今日运势)$", text):
                async for r in daily_fortune_handler(event, self.music_data):
                    yield r
                    return

            # mai什么 / 随机歌曲
            if re.match(r"^.*mai.*什么", text):
                async for r in mai_what_handler(event, self.music_data):
                    yield r
                    return

            # 来/随/给个 + 难度
            if re.match(r"^[来随给]个", text):
                async for r in random_song_handler(event, self.music_data):
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
                qq = self._get_qq(event)
                # 等级进度以数字开头（如 "12 SSS进度"），版牌进度以版本字开头（如 "真極进度"）
                if re.match(r"^\d", text):
                    async for r in mai_level_progress_handler(event, self.api, self.music_data, qq=qq):
                        yield r
                    return
                async for r in mai_plate_progress_handler(event, self.api, self.music_data, qq=qq):
                    yield r
                return

            # 推分
            if re.match(r"^我要在", text):
                prober = self._get_prober(event, "maimai")
                lxns_token = await self._get_lxns_token(event)
                qq = self._get_qq(event)
                async for r in mai_rise_score_handler(event, self.api, self.music_data, prober=prober, lxns=self.lxns, lxns_token=lxns_token, qq=qq):
                    yield r
                return

        # --- 共用：别名相关（按游戏路由） ---

        if re.search(r"有什么别[名称]$", text):
            if game == "chunithm":
                async for r in chu_alias_query_handler(event, self.chu_data):
                    yield r
            else:
                async for r in alias_query_handler(event, self.music_data):
                    yield r
            return

        if re.search(r"(是什么歌|是啥歌)$", text):
            if game == "chunithm":
                async for r in chu_search_alias_handler(event, self.chu_data):
                    yield r
            else:
                async for r in mai_search_alias_handler(event, self.music_data):
                    yield r
            return
