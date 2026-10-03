"""同步数据：SGWCMAID 二维码同步到水鱼/落雪查分器。"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from ..qr_sync import extract_sgid, is_valid_sgid

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


class SyncService:
    """同步服务：封装「同步数据」命令与 SGID 等待状态。"""

    def __init__(
        self,
        *,
        user_store,
        get_qr_sync,
        get_lxns_token,
        user_key_of,
        message,
    ) -> None:
        self.user_store = user_store
        self._get_qr_sync = get_qr_sync
        self._get_lxns_token = get_lxns_token
        self._user_key_of = user_key_of
        self._message = message
        # 同步数据等待状态: {user_key: (prober, expire_timestamp)}
        self._pending_sync: dict[str, tuple[str, float]] = {}

    @property
    def qr_sync(self):
        return self._get_qr_sync()

    def has_pending(self, user_key: str) -> bool:
        return user_key in self._pending_sync

    async def start(self, event: "AstrMessageEvent"):
        """同步街机数据到查分器。用法：同步数据 水鱼/落雪"""
        args = event.get_message_str().strip().split(maxsplit=1)
        target = args[1].strip().lower() if len(args) > 1 else ""

        user_key = self._user_key_of(event)
        lxns_token = await self._get_lxns_token(event)
        df_token = self.user_store.get_divingfish_token(user_key)

        if target in ("水鱼", "divingfish", "df"):
            if not df_token:
                yield self._message(event, "⚠️ 未绑定水鱼查分器，请先发送「绑定水鱼 <Token>」。")
                return
            prober = "divingfish"
            label = "水鱼"
        elif target in ("落雪", "lxns"):
            if not lxns_token:
                yield self._message(event, "⚠️ 未绑定落雪查分器，请先发送「绑定落雪」。")
                return
            prober = "lxns"
            label = "落雪"
        else:
            yield self._message(event, "用法：同步数据 水鱼/落雪")
            return

        self._pending_sync[user_key] = (prober, time.time() + 3 * 60)
        yield self._message(
            event,
            f"🔗 请在 **3 分钟内** 发送街机二维码（SGWCMAID...），将同步到{label}查分器。",
        )

        async def _timeout():
            await asyncio.sleep(3 * 60)
            if self._pending_sync.pop(user_key, None):
                try:
                    result = event.make_result().message("⏰ 同步超时，请重新发送「同步数据 水鱼/落雪」。")
                    await event.send(result)
                except Exception:
                    pass
        asyncio.create_task(_timeout())

    async def try_sync_sgid(self, event: "AstrMessageEvent", sgid: str = ""):
        """等待中的同步：收到 SGID 后执行同步。"""
        if not sgid:
            sgid = extract_sgid(event.get_message_str()) or ""
        if not sgid:
            return

        user_key = self._user_key_of(event)
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

        yield self._message(event, f"🎮 正在同步成绩到{label}，请稍候...")

        qr = self.qr_sync
        if qr is None:
            yield self._message(event, "❌ QR 同步服务未初始化（缺少 maimai-py）。")
            return

        try:
            if prober == "lxns":
                result = await qr.sync_to_lxns(sgid, lxns_token)
            else:
                result = await qr.sync_to_divingfish(sgid, df_token)

            lines = [
                "✅ 同步成功！",
                f"  玩家: {result.player_name}" if result.player_name else "",
                f"  Rating: {result.rating}",
                f"  同步曲数: {result.score_count}",
            ]
            if result.warning:
                lines.append(f"  ⚠️ {result.warning}")
            yield self._message(event, "\n".join(lines))

        except Exception as e:
            err_msg = qr.describe_error(e)
            logger.exception("同步数据失败")
            yield self._message(event, f"❌ {err_msg}")
