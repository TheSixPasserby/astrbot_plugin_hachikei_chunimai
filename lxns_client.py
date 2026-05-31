"""落雪查分器 (Lxns) API 客户端，支持 maimai DX 和 CHUNITHM。"""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .errors import MaimaiError, ServerError, UserNotFoundError

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class LxnsAPI:
    """落雪查分器 API 客户端。"""

    BASE_URL = "https://maimai.lxns.net/api/v0"

    # --- 游戏资源 ---
    MAIMAI_ASSETS = "https://assets2.lxns.net/maimai"
    CHUNITHM_ASSETS = "https://assets2.lxns.net/chunithm"

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout
        self._dev_key: str = ""
        self._user_token: str = ""
        self._session: ClientSession | None = None

    def configure(self, dev_key: str = "", user_token: str = "") -> None:
        self._dev_key = dev_key
        self._user_token = user_token

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=ClientTimeout(total=self._timeout))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _dev_headers(self) -> dict[str, str]:
        if self._dev_key:
            return {"Authorization": self._dev_key}
        return {}

    def _user_headers(self) -> dict[str, str]:
        if self._user_token:
            return {"X-User-Token": self._user_token}
        return {}

    async def _get(self, path: str, headers: dict | None = None, **kwargs: Any) -> Any:
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"
        async with session.get(url, headers=headers or self._dev_headers(), **kwargs) as res:
            data = await res.json()
            if not data.get("success"):
                code = data.get("code", res.status)
                msg = data.get("message", "未知错误")
                if code == 404 or "not found" in str(msg).lower():
                    raise UserNotFoundError
                raise ServerError(f"Lxns API 错误 ({code}): {msg}")
            return data.get("data")

    # ================================================================
    # maimai DX
    # ================================================================

    async def mai_player_by_qq(self, qq: int) -> dict:
        return await self._get(f"/maimai/player/qq/{qq}")

    async def mai_player_by_fc(self, friend_code: int) -> dict:
        return await self._get(f"/maimai/player/{friend_code}")

    async def mai_bests(self, friend_code: int) -> dict:
        """获取 Best 50。返回 {standard_total, dx_total, standard[], dx[]}"""
        return await self._get(f"/maimai/player/{friend_code}/bests")

    async def mai_best(self, friend_code: int, **params) -> dict:
        """获取单曲最佳成绩。"""
        return await self._get(f"/maimai/player/{friend_code}/best", params=params)

    async def mai_scores(self, friend_code: int) -> list:
        """获取所有成绩（简化）。"""
        return await self._get(f"/maimai/player/{friend_code}/scores")

    async def mai_recents(self, friend_code: int) -> list:
        """获取 Recent 50。"""
        return await self._get(f"/maimai/player/{friend_code}/recents")

    async def mai_song_list(self, **params) -> dict:
        """获取曲目列表。返回 {songs[], genres[], versions[]}"""
        return await self._get("/maimai/song/list", params=params)

    async def mai_song(self, song_id: int) -> dict:
        return await self._get(f"/maimai/song/{song_id}")

    async def mai_alias_list(self) -> dict:
        """获取别名列表。返回 {aliases[]}"""
        return await self._get("/maimai/alias/list")

    # ================================================================
    # CHUNITHM
    # ================================================================

    async def chu_player_by_qq(self, qq: int) -> dict:
        return await self._get(f"/chunithm/player/qq/{qq}")

    async def chu_player_by_fc(self, friend_code: int) -> dict:
        return await self._get(f"/chunithm/player/{friend_code}")

    async def chu_bests(self, friend_code: int) -> dict:
        """获取 Rating 构成。返回 {bests[], selections[], new_bests[]}"""
        return await self._get(f"/chunithm/player/{friend_code}/bests")

    async def chu_best(self, friend_code: int, **params) -> dict:
        """获取单曲最佳成绩。"""
        return await self._get(f"/chunithm/player/{friend_code}/best", params=params)

    async def chu_scores(self, friend_code: int) -> list:
        """获取所有成绩（简化）。"""
        return await self._get(f"/chunithm/player/{friend_code}/scores")

    async def chu_recents(self, friend_code: int) -> list:
        """获取 Recent 50。"""
        return await self._get(f"/chunithm/player/{friend_code}/recents")

    async def chu_song_list(self, **params) -> dict:
        """获取曲目列表。返回 {songs[], genres[], versions[]}"""
        return await self._get("/chunithm/song/list", params=params)

    async def chu_song(self, song_id: int) -> dict:
        return await self._get(f"/chunithm/song/{song_id}")

    async def chu_alias_list(self) -> dict:
        """获取别名列表。返回 {aliases[]}"""
        return await self._get("/chunithm/alias/list")

    # ================================================================
    # 游戏资源 URL
    # ================================================================

    @staticmethod
    def mai_jacket_url(song_id: int) -> str:
        return f"{LxnsAPI.MAIMAI_ASSETS}/jacket/{song_id}.png"

    @staticmethod
    def chu_jacket_url(song_id: int) -> str:
        return f"{LxnsAPI.CHUNITHM_ASSETS}/jacket/{song_id}.png"
