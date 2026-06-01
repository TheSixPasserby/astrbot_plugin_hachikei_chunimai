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

    async def _user_get(self, path: str, **kwargs: Any) -> Any:
        """使用个人 API 密钥请求。"""
        return await self._get(path, headers=self._user_headers(), **kwargs)

    # ================================================================
    # OAuth2
    # ================================================================

    async def oauth_user_profile(self) -> dict:
        """用 OAuth token 获取用户 profile（含 friend_code）。"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/user/profile"
        headers = {"Authorization": f"Bearer {self._user_token}"}
        async with session.get(url, headers=headers) as res:
            data = await res.json()
            logger.info(f"OAuth profile 响应: {data}")
            if not data.get("success"):
                msg = data.get("message", "未知错误")
                raise ServerError(f"获取用户 profile 失败: {msg}")
            return data.get("data", data)

    async def oauth_exchange(self, code: str, client_id: str, client_secret: str, redirect_uri: str) -> str:
        """用授权码换取 access_token。返回 token 字符串。"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
        async with session.post(url, json=payload) as res:
            data = await res.json()
            logger.info(f"OAuth 响应: {data}")
            if not data.get("success"):
                msg = data.get("message", "未知错误")
                raise ServerError(f"OAuth 交换失败: {msg}")
            token = data["data"].get("access_token", data["data"].get("token", ""))
            if not token:
                raise ServerError(f"OAuth 响应中无 token: {data}")
            return token

    # ================================================================
    # maimai DX（开发者 API）
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

    # ================================================================
    # maimai DX（个人 API）
    # ================================================================

    async def mai_user_player(self) -> dict:
        """获取自己的玩家信息。"""
        return await self._user_get("/user/maimai/player")

    async def mai_user_scores(self) -> list:
        """获取自己的所有成绩。"""
        return await self._user_get("/user/maimai/player/scores")

    async def mai_song_list(self, **params) -> dict:
        """获取曲目列表。返回 {songs[], genres[], versions[]}"""
        # 公共 API，不带认证头
        session = await self._get_session()
        url = f"{self.BASE_URL}/maimai/song/list"
        async with session.get(url, params=params) as res:
            data = await res.json()
            if isinstance(data, dict) and "songs" in data:
                return data
            if not data.get("success"):
                raise ServerError(f"落雪歌曲API: {data.get('message', '未知错误')}")
            return data.get("data", data)

    async def mai_song(self, song_id: int) -> dict:
        return await self._get(f"/maimai/song/{song_id}")

    async def mai_alias_list(self) -> dict:
        """获取别名列表（公共 API）。返回 {aliases[]}"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/maimai/alias/list"
        async with session.get(url) as res:
            data = await res.json()
            if isinstance(data, dict) and "aliases" in data:
                return data
            if not data.get("success"):
                raise ServerError(f"落雪舞萌别名API: {data.get('message', '未知错误')}")
            return data.get("data", data)

    # ================================================================
    # CHUNITHM（开发者 API）
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

    # ================================================================
    # CHUNITHM（个人 API）
    # ================================================================

    async def chu_user_player(self) -> dict:
        """获取自己的玩家信息。"""
        return await self._user_get("/user/chunithm/player")

    async def chu_user_scores(self) -> list:
        """获取自己的所有成绩。"""
        return await self._user_get("/user/chunithm/player/scores")

    async def chu_song_list(self, **params) -> dict:
        """获取曲目列表。返回 {songs[], genres[], versions[]}"""
        # 公共 API，不带认证头
        session = await self._get_session()
        url = f"{self.BASE_URL}/chunithm/song/list"
        async with session.get(url, params=params) as res:
            data = await res.json()
            if isinstance(data, dict) and "songs" in data:
                return data
            if not data.get("success"):
                raise ServerError(f"落雪CHUNITHM歌曲API: {data.get('message', '未知错误')}")
            return data.get("data", data)

    async def chu_song(self, song_id: int) -> dict:
        return await self._get(f"/chunithm/song/{song_id}")

    async def chu_alias_list(self) -> dict:
        """获取别名列表（公共 API）。返回 {aliases[]}"""
        session = await self._get_session()
        url = f"{self.BASE_URL}/chunithm/alias/list"
        async with session.get(url) as res:
            data = await res.json()
            if isinstance(data, dict) and "aliases" in data:
                return data
            if not data.get("success"):
                raise ServerError(f"落雪CHUNITHM别名API: {data.get('message', '未知错误')}")
            return data.get("data", data)

    # ================================================================
    # 游戏资源 URL
    # ================================================================

    @staticmethod
    def mai_jacket_url(song_id: int) -> str:
        return f"{LxnsAPI.MAIMAI_ASSETS}/jacket/{song_id}.png"

    @staticmethod
    def chu_jacket_url(song_id: int) -> str:
        return f"{LxnsAPI.CHUNITHM_ASSETS}/jacket/{song_id}.png"
