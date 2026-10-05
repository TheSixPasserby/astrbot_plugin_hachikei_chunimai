"""管理命令：切换游戏/查分器/别名源、群功能开关、数据更新、插件状态。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..mai_data import MusicDataManager

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..chu_data import ChuDataManager
    from ..storage import GroupConfigStore, UserStore

GAME_LABELS = {"maimai": "maimai DX", "chunithm": "CHUNITHM"}
_GAME_ALIASES = {"舞萌": "maimai", "maimai": "maimai", "中二": "chunithm", "chunithm": "chunithm"}
_PROBER_MAP = {"水鱼": "divingfish", "落雪": "lxns", "divingfish": "divingfish", "lxns": "lxns"}


class AdminService:
    """管理命令服务。"""

    def __init__(
        self,
        *,
        user_store: "UserStore",
        group_store: "GroupConfigStore",
        config: dict,
        context,
        music_data: MusicDataManager,
        chu_data: "ChuDataManager",
        get_qr_sync,
        is_admin,
        group_id_of,
        user_key_of,
        message,
    ) -> None:
        self.user_store = user_store
        self.group_store = group_store
        self.config = config
        self.context = context
        self.music_data = music_data
        self.chu_data = chu_data
        self._get_qr_sync = get_qr_sync
        self._is_admin = is_admin
        self._group_id_of = group_id_of
        self._user_key_of = user_key_of
        self._message = message

    def get_prober(self, event: "AstrMessageEvent", game: str) -> str:
        """获取当前群指定游戏的查分器。"""
        gid = self._group_id_of(event)
        return self.group_store.get_prober(game, gid)

    async def switch_game(self, event: "AstrMessageEvent"):
        """切换查询游戏。用法：更改游戏 舞萌/中二"""
        args = event.get_message_str().strip().split()

        if len(args) < 2:
            yield self._message(event, "用法：更改游戏 舞萌/中二")
            return

        sub = args[1].lower()

        # 群默认（管理员）
        if sub in ("group", "群"):
            if not self._is_admin(event):
                yield self._message(event, "需要管理员权限。")
                return
            if len(args) < 3:
                yield self._message(event, "用法: 更改游戏 群 舞萌/中二")
                return
            game = _GAME_ALIASES.get(args[2].lower())
            if not game:
                yield self._message(event, "无效游戏。可选: 舞萌、中二")
                return
            gid = self._group_id_of(event)
            if not gid:
                yield self._message(event, "此命令只能在群聊中使用。")
                return
            await self.group_store.set_group_game_mode(gid, game)
            label = GAME_LABELS.get(game, game)
            yield self._message(event, f"✅ 群默认查询游戏已设为 {label}。")
            return

        # 个人设置
        game = _GAME_ALIASES.get(sub)
        if not game:
            yield self._message(event, "无效游戏。可选: 舞萌、中二")
            return
        user_key = self._user_key_of(event)
        await self.user_store.set_game_mode(user_key, game)
        label = GAME_LABELS.get(game, game)
        yield self._message(event, f"✅ 个人查询游戏已设为 {label}。")

    async def switch_prober(self, event: "AstrMessageEvent"):
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
            yield self._message(event, "用法：更改查分器 水鱼/落雪")
            return

        prober = _PROBER_MAP.get(prober_input)
        if not prober:
            yield self._message(event, "无效查分器。可选：水鱼、落雪")
            return

        group_id = self._group_id_of(event)
        if not group_id:
            yield self._message(event, "此命令只能在群聊中使用。")
            return

        await self.group_store.set_prober("maimai", prober, group_id)
        prober_label = "水鱼" if prober == "divingfish" else "落雪"
        yield self._message(event, f"✅ 舞萌查分器已切换为 {prober_label}。")

    async def plugin_status(self, event: "AstrMessageEvent"):
        """管理员查看各子系统就绪状态。"""
        if not self._is_admin(event):
            yield self._message(event, "需要管理员权限。")
            return

        def _ok(flag: bool) -> str:
            return "OK" if flag else "FAIL"

        qr = self._get_qr_sync()
        lines = [
            "📊 **插件状态**",
            "",
            "| 子系统 | 状态 |",
            "|--------|------|",
            f"| maimai 曲库 | {_ok(self.music_data.music_list is not None and len(self.music_data.music_list) > 0)} |",
            f"| maimai 别名 | {_ok(len(self.music_data.alias_list) > 0)} |",
            f"| CHUNITHM 曲库 | {_ok(len(self.chu_data.songs) > 0)} |",
            f"| Lxns API | {_ok(bool(self.config.get('lxns_dev_key', '')))} |",
            f"| DivingFish | {_ok(bool(self.config.get('mai_divingfish_token', '')))} |",
            f"| maimai-py | {_ok(qr is not None)} |",
            f"| QR Sync | {_ok(qr is not None)} |",
            f"| HTTP 代理 | {self.config.get('http_proxy', '') or '未配置'} |",
        ]
        yield self._message(event, "\n".join(lines))

    async def toggle_maimai(self, event: "AstrMessageEvent"):
        if not self._is_admin(event):
            yield self._message(event, "需要管理员权限。")
            return
        text = event.get_message_str().strip()
        enable = "开启" in text
        group_id = self._group_id_of(event)
        if not group_id:
            yield self._message(event, "此命令只能在群聊中使用。")
            return
        await self.group_store.toggle_group(group_id, enable)
        status = "开启" if enable else "关闭"
        yield self._message(event, f"✅ 群功能已{status}。")

    async def switch_alias_source(self, event: "AstrMessageEvent"):
        if not self._is_admin(event):
            yield self._message(event, "需要管理员权限。")
            return
        text = event.get_message_str().strip()
        m = re.search(r"(舞萌|maimai|中二|chunithm)\s*(水鱼|yuzuchan|落雪|lxns)", text, re.IGNORECASE)
        if not m:
            yield self._message(
                event,
                "用法：更改别名源 <游戏> <数据源>\n"
                "游戏：舞萌 / 中二\n"
                "数据源：水鱼 / 落雪\n"
                "例如：更改别名源 舞萌 落雪",
            )
            return

        game_raw = m.group(1).lower()
        source_raw = m.group(2).lower()

        game = "maimai" if game_raw in ("舞萌", "maimai") else "chunithm"
        source = "lxns" if source_raw in ("落雪", "lxns") else "yuzuchan"

        if game == "chunithm" and source == "yuzuchan":
            yield self._message(event, "中二节奏暂不支持柚子别名源，请使用落雪。")
            return

        key = "mai_alias_source" if game == "maimai" else "chu_alias_source"
        self.config[key] = source
        try:
            self.context.save_config()
        except Exception:
            pass

        label = "舞萌" if game == "maimai" else "中二"
        src_label = "落雪" if source == "lxns" else "柚子"
        yield self._message(event, f"🔄 正在从{src_label}重新加载{label}别名数据...")

        if game == "maimai":
            self.music_data.configure_alias(source=source, lxns=self.music_data.lxns)
            try:
                await self.music_data.load_alias_data()
                yield self._message(event, f"✅ {label}别名源已切换为 {src_label}，共 {len(self.music_data.alias_list)} 条。")
            except Exception as e:
                yield self._message(event, f"❌ 加载别名失败：{e}")
        else:
            try:
                await self.chu_data.load_aliases()
                yield self._message(event, f"✅ {label}别名源已切换为 {src_label}，共 {len(self.chu_data.aliases)} 条。")
            except Exception as e:
                yield self._message(event, f"❌ 加载别名失败：{e}")

    async def update_data(self, event: "AstrMessageEvent"):
        if not self._is_admin(event):
            yield self._message(event, "需要管理员权限。")
            return
        try:
            await self.music_data.load_all()
            yield self._message(
                event,
                f"✅ 数据已更新：{len(self.music_data.music_list)} 首歌曲，"
                f"{len(self.music_data.alias_list)} 条别名",
            )
        except Exception as e:
            yield self._message(event, f"更新失败：{e}")
