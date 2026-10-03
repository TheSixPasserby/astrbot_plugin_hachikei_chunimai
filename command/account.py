"""账号绑定：绑定/解绑 QQ、落雪 OAuth、水鱼 Import-Token，账号状态。

封装绑定相关的 pending 状态（OAuth 密钥等待 / 水鱼 Token 等待），
命令 handler 只依赖 ``AccountService``，不直接碰 main.py 的内部状态。
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Any

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..lxns_client import LxnsAPI
    from ..storage import GroupConfigStore, UserStore

_OAUTH_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
_OAUTH_SCOPE = "read_user_profile+read_player+write_player"


def _user_key(event: "AstrMessageEvent") -> str:
    return f"{event.get_platform_name()}:{event.get_sender_id()}"


def _group_id(event: "AstrMessageEvent") -> str:
    """跨平台获取群/频道 ID。"""
    gid = event.get_group_id()
    if gid:
        return str(gid)
    try:
        msg = event.message_obj
        for attr in ("group_id", "channel_id", "group_openid"):
            val = getattr(msg, attr, None)
            if val:
                return str(val)
    except Exception:
        pass
    try:
        sid = event.session_id
        if sid:
            return str(sid)
    except Exception:
        pass
    return ""


class AccountService:
    """账号绑定服务：封装 OAuth / 水鱼 Token 的等待状态与业务逻辑。"""

    def __init__(
        self,
        user_store: "UserStore",
        group_store: "GroupConfigStore",
        config: dict,
        lxns: "LxnsAPI",
    ) -> None:
        self.user_store = user_store
        self.group_store = group_store
        self.config = config
        self.lxns = lxns

        # OAuth 绑定等待状态: {user_key: expire_timestamp}
        self._pending_oauth: dict[str, float] = {}
        # 水鱼 Token 等待状态: {user_key: expire_timestamp}
        self._pending_df: dict[str, float] = {}
        # token 失效的用户
        self._expired_tokens: set[str] = set()
        # 水鱼绑定成功后的临时消息（由 _on_message 消费）
        self._pending_df_message: str | None = None

    @staticmethod
    def _message(event: "AstrMessageEvent", text: str):
        return event.make_result().message(text)

    async def bind_qq(self, event: "AstrMessageEvent"):
        args = event.get_message_str().strip().split()
        if len(args) < 2 or not args[1].isdigit():
            yield self._message(event, "用法：绑定QQ <QQ号>\n绑定后查分命令将使用该 QQ 号查询。")
            return
        qq = args[1].strip()
        user_key = _user_key(event)
        await self.user_store.set_qq(user_key, qq)
        yield self._message(event, f"✅ 已绑定 QQ: {qq}")

    async def bind_lxns(self, event: "AstrMessageEvent"):
        """落雪 OAuth 绑定 — 生成链接，等待用户发送密钥。"""
        client_id = self.config.get("lxns_client_id", "")
        client_secret = self.config.get("lxns_client_secret", "")

        if not client_id or not client_secret:
            yield self._message(
                event,
                "⚠️ 管理员未配置落雪 OAuth 应用。\n"
                "请在插件配置中填写 `lxns_client_id` 和 `lxns_client_secret`。",
            )
            return

        oauth_url = (
            f"https://maimai.lxns.net/oauth/authorize"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={_OAUTH_REDIRECT}"
            f"&scope={_OAUTH_SCOPE}"
        )

        user_key = _user_key(event)
        self._pending_oauth[user_key] = time.time() + 5 * 60

        yield self._message(
            event,
            f"🔗 请点击链接授权落雪查分器：\n{oauth_url}\n\n"
            f"授权后页面会显示一串密钥，请在 **5 分钟内** 直接发送到聊天窗口即可。",
        )

        async def _timeout():
            await asyncio.sleep(5 * 60)
            if self._pending_oauth.pop(user_key, None):
                try:
                    result = event.make_result().message("⏰ 落雪绑定超时，请重新发送 `绑定落雪` 获取新链接。")
                    await event.send(result)
                except Exception:
                    pass
        asyncio.create_task(_timeout())

    async def try_oauth_code(self, event: "AstrMessageEvent"):
        """检测用户是否在等待发送 OAuth 密钥。如果是，尝试交换。"""
        user_key = _user_key(event)
        expire = self._pending_oauth.get(user_key)
        if not expire:
            return
        if time.time() > expire:
            del self._pending_oauth[user_key]
            return

        text = event.get_message_str().strip()
        # 密钥格式：通常 30 位左右的字母数字
        if len(text) < 10 or len(text) > 60 or " " in text:
            return

        client_id = self.config.get("lxns_client_id", "")
        client_secret = self.config.get("lxns_client_secret", "")
        logger.info(f"[oauth] 用户 {user_key} 尝试交换 code")

        try:
            access_token, refresh_token = await self.lxns.oauth_exchange(
                text, client_id, client_secret, _OAUTH_REDIRECT
            )
        except Exception as e:
            logger.debug(f"OAuth 交换尝试失败（非密钥消息）: {e}")
            return

        del self._pending_oauth[user_key]
        self._expired_tokens.discard(user_key)
        await self.user_store.set_lxns_token(
            user_key, access_token, refresh_token, expires_at=time.time() + 15 * 60
        )

        gid = _group_id(event)
        if gid:
            await self.group_store.set_prober("maimai", "lxns", gid)

        yield self._message(
            event,
            "✅ 落雪查分器绑定成功！已自动切换舞萌查分器为落雪。\n"
            "如需使用水鱼查分器，请发送：更改查分器 水鱼",
        )

    async def unbind_lxns(self, event: "AstrMessageEvent"):
        """解绑落雪查分器。"""
        user_key = _user_key(event)
        token = self.user_store.get_lxns_token(user_key)
        if not token:
            yield self._message(event, "你还没有绑定落雪查分器。")
            return
        await self.user_store.remove_lxns_token(user_key)
        yield self._message(event, "✅ 已解绑落雪查分器。")

    async def bind_divingfish(self, event: "AstrMessageEvent"):
        """绑定水鱼 Import-Token。"""
        args = event.get_message_str().strip().split(maxsplit=1)

        if len(args) >= 2:
            token = args[1].strip()
            if len(token) < 50:
                yield self._message(event, "Token 格式不正确，请检查后重试。")
                return
            user_key = _user_key(event)
            async for r in self.df_bind_and_switch(event, user_key, token):
                yield r
            return

        user_key = _user_key(event)
        self._pending_df[user_key] = time.time() + 5 * 60
        yield self._message(
            event,
            "🔗 请前往水鱼查分器获取 Import-Token：\n"
            "https://maimai.diving-fish.com/\n\n"
            "1. 登录查分器\n"
            "2. 点击右上角「编辑个人资料」\n"
            "3. 复制「成绩导入 Token」\n"
            "4. 在 **5 分钟内** 直接发送到聊天窗口即可",
        )

        async def _timeout():
            await asyncio.sleep(5 * 60)
            if self._pending_df.pop(user_key, None):
                try:
                    result = event.make_result().message("⏰ 水鱼绑定超时，请重新发送「绑定水鱼」。")
                    await event.send(result)
                except Exception:
                    pass
        asyncio.create_task(_timeout())

    async def try_df_token(self, event: "AstrMessageEvent") -> bool:
        """检测用户是否在等待发送水鱼 Token。"""
        user_key = _user_key(event)
        expire = self._pending_df.get(user_key)
        if not expire or time.time() > expire:
            self._pending_df.pop(user_key, None)
            return False

        text = event.get_message_str().strip()
        # QQ Official 消息中 @bot 会混入文本，去掉 @mention 部分
        text = re.sub(r"@\S+\s*", "", text).strip()
        if len(text) < 50 or len(text) > 300 or " " in text:
            return False

        del self._pending_df[user_key]
        await self.user_store.set_divingfish_token(user_key, text)
        gid = _group_id(event)
        if gid:
            await self.group_store.set_prober("maimai", "divingfish", gid)
        self._pending_df_message = (
            "✅ 水鱼查分器绑定成功！已自动切换舞萌查分器为水鱼。\n"
            "如需使用落雪查分器，请发送：更改查分器 落雪"
        )
        return True

    async def df_bind_and_switch(self, event: "AstrMessageEvent", user_key: str, token: str):
        """绑定水鱼 Token 并自动切换查分器。"""
        await self.user_store.set_divingfish_token(user_key, token)
        gid = _group_id(event)
        if gid:
            await self.group_store.set_prober("maimai", "divingfish", gid)
        yield self._message(
            event,
            "✅ 水鱼查分器绑定成功！已自动切换舞萌查分器为水鱼。\n"
            "如需使用落雪查分器，请发送：更改查分器 落雪",
        )

    async def unbind_divingfish(self, event: "AstrMessageEvent"):
        """解绑水鱼 Import-Token。"""
        user_key = _user_key(event)
        token = self.user_store.get_divingfish_token(user_key)
        if not token:
            yield self._message(event, "你还没有绑定水鱼查分器。")
            return
        await self.user_store.remove_divingfish_token(user_key)
        yield self._message(event, "✅ 已解绑水鱼查分器。")

    async def account_status(self, event: "AstrMessageEvent"):
        """查看当前账号绑定状态。"""
        user_key = _user_key(event)

        qq = self.user_store.get_qq(user_key)
        qq_status = f"✅ {qq}" if qq else "❌ 未绑定"

        lxns_token = self.user_store.get_lxns_token(user_key)
        token_expired = user_key in self._expired_tokens
        if lxns_token:
            lxns_status = "✅ 已授权"
        elif token_expired:
            lxns_status = "⚠️ 已失效"
        else:
            lxns_status = "❌ 未绑定"

        df_token = self.user_store.get_divingfish_token(user_key)
        divingfish_status = "✅ 已绑定" if df_token else "❌ 未绑定"

        lines = [
            "📋 **账号绑定状态**\n",
            f"| 项目 | 状态 |",
            f"|------|------|",
            f"| QQ 号 | {qq_status} |",
            f"| 落雪查分器 | {lxns_status} |",
            f"| 水鱼查分器 | {divingfish_status} |",
            "",
        ]

        if token_expired:
            lines.append("⚠️ **落雪授权已失效**，请重新绑定。")
            lines.append("")

        lines.extend([
            "---",
            "**绑定指引：**",
            "• `绑定QQ <QQ号>` — 绑定 QQ",
            "• `绑定落雪` — 授权落雪查分器（推荐）",
            "• `绑定水鱼` — 获取水鱼 Import-Token",
            "• `解绑落雪` / `解绑水鱼` — 取消授权",
        ])
        if not qq and not lxns_token:
            lines.append("")
            lines.append("⚠️ 你还没有绑定任何查分方式，请先绑定 QQ 或落雪。")

        yield self._message(event, "\n".join(lines))
