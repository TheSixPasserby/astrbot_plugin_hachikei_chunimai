"""HTTP API 客户端：DivingFish 查分器 + Yuzuchan 别名服务器。"""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .errors import (
    UserNotFoundError, UserNotExistsError, UserDisabledQueryError,
    TokenError, TokenDisableError, TokenNotFoundError,
    ServerError, MusicNotPlayError,
)
from .models import (
    APIResult, Alias, AliasStatus, Music, PlayInfoDefault, PlayInfoDev,
    UserInfo, UserInfoDev, UserRanking,
)


class MaimaiAPI:
    """封装所有外部 HTTP API 调用。"""

    MaiProxyAPI = "https://proxy.yuzuchan.site"
    MaiProberAPI = "https://www.diving-fish.com/api/maimaidxprober"
    MaiAliasAPI = "https://www.yuzuchan.moe/api/maimaidx"

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout
        self.token: str | None = None
        self.headers: dict[str, str] | None = None
        self.use_proxy: bool = False
        self._session: ClientSession | None = None

    def configure(self, token: str = "", proxy: bool = False) -> None:
        self.use_proxy = proxy
        self.token = token
        if token:
            self.headers = {"developer-token": token}

    @property
    def prober_url(self) -> str:
        base = self.MaiProxyAPI + "/maimaidxprober" if self.use_proxy else self.MaiProberAPI
        return base

    @property
    def alias_url(self) -> str:
        base = self.MaiProxyAPI + "/maimaidxaliases" if self.use_proxy else self.MaiAliasAPI
        return base

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=ClientTimeout(total=self._timeout))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request_prober(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict | list:
        session = await self._get_session()
        async with session.request(
            method, self.prober_url + endpoint, headers=self.headers, **kwargs
        ) as res:
            if res.status == 200:
                return await res.json()
            if res.status == 400:
                error = await res.json()
                if "message" in error:
                    msg = error["message"]
                    if msg == "no such user":
                        raise UserNotFoundError
                    if msg == "user not exists":
                        raise UserNotExistsError
                    raise UserNotFoundError
                if "msg" in error:
                    msg = error["msg"]
                    if "token有误" in msg:
                        raise TokenError
                    if "token被禁用" in msg:
                        raise TokenDisableError
                    raise TokenNotFoundError
                raise UserNotFoundError
            if res.status == 403:
                raise UserDisabledQueryError
            raise ServerError(f"HTTP {res.status}")

    async def _request_alias(self, method: str, endpoint: str, **kwargs: Any) -> APIResult:
        session = await self._get_session()
        async with session.request(
            method, self.alias_url + endpoint, **kwargs
        ) as res:
            if res.status == 200:
                data = await res.json()
                return APIResult.model_validate(data)
            if res.status == 500:
                raise ServerError("别名服务器错误")
            raise ServerError(f"别名服务器 HTTP {res.status}")

    # --- 查分器 API ---

    async def music_data(self) -> list[dict]:
        return await self._request_prober("GET", "/music_data")

    async def chart_stats(self) -> dict:
        return await self._request_prober("GET", "/chart_stats")

    async def query_user_b50(
        self, *, qqid: int | None = None, username: str | None = None
    ) -> UserInfo:
        payload: dict[str, Any] = {"b50": True}
        if qqid:
            payload["qq"] = qqid
        if username:
            payload["username"] = username
        data = await self._request_prober("POST", "/query/player", json=payload)
        return UserInfo.model_validate(data)

    async def query_user_plate(
        self,
        *,
        qqid: int | None = None,
        username: str | None = None,
        version: list[str] | None = None,
    ) -> list[PlayInfoDefault]:
        payload: dict[str, Any] = {}
        if qqid:
            payload["qq"] = qqid
        if username:
            payload["username"] = username
        if version:
            payload["version"] = version
        data = await self._request_prober("POST", "/query/plate", json=payload)
        return [PlayInfoDefault.model_validate(d) for d in data["verlist"]]

    async def query_user_dev(
        self, *, qqid: int | None = None, username: str | None = None
    ) -> UserInfoDev:
        params: dict[str, Any] = {}
        if qqid:
            params["qq"] = qqid
        if username:
            params["username"] = username
        data = await self._request_prober("GET", "/dev/player/records", params=params)
        return UserInfoDev.model_validate(data)

    async def query_user_record_dev(
        self,
        *,
        qqid: int | None = None,
        username: str | None = None,
        music_id: int | str | list[int | str],
    ) -> list[PlayInfoDev]:
        payload: dict[str, Any] = {"music_id": music_id}
        if qqid:
            payload["qq"] = qqid
        if username:
            payload["username"] = username
        data = await self._request_prober("POST", "/dev/player/record", json=payload)
        if data == {}:
            raise MusicNotPlayError
        if isinstance(music_id, list):
            return [PlayInfoDev.model_validate(d) for v in data.values() for d in v]
        return [PlayInfoDev.model_validate(d) for d in data[str(music_id)]]

    async def rating_ranking(self) -> list[UserRanking]:
        data = await self._request_prober("GET", "/rating_ranking")
        return sorted(
            [UserRanking.model_validate(u) for u in data],
            key=lambda x: x.ra,
            reverse=True,
        )

    # --- 别名服务器 API ---

    async def get_alias(self) -> dict:
        result = await self._request_alias("GET", "/maimaidxalias")
        if result.code == 0:
            return result.content
        raise ServerError("获取别名失败")

    async def get_songs(self, name: str) -> list[Alias] | list[AliasStatus]:
        result = await self._request_alias("GET", "/getsongs", params={"name": name})
        if result.code == 0:
            return [Alias.model_validate(s) for s in result.content]
        if result.code == 3006:
            return [AliasStatus.model_validate(s) for s in result.content]
        if result.code == 1004:
            return []
        raise ServerError("别名查询失败")

    async def get_songs_alias(self, song_id: int) -> Alias | str:
        result = await self._request_alias(
            "GET", "/getsongsalias", params={"song_id": song_id}
        )
        if result.code == 0:
            return Alias.model_validate(result.content)
        if result.code == 1004:
            return result.content
        raise ServerError("别名查询失败")

    async def get_alias_status(self) -> list[AliasStatus]:
        result = await self._request_alias("GET", "/getaliasstatus")
        if result.code == 0:
            return [AliasStatus.model_validate(s) for s in result.content]
        if result.code == 1004:
            return []
        raise ServerError("获取投票状态失败")

    async def post_alias(
        self, song_id: int, alias_name: str, user_id: int, group_id: int, uuid: str
    ) -> Any:
        payload = {
            "SongID": song_id,
            "ApplyAlias": alias_name,
            "ApplyUID": user_id,
            "GroupID": group_id,
            "WSUUID": str(uuid),
        }
        result = await self._request_alias("POST", "/applyalias", json=payload)
        return result.content

    async def post_agree_user(self, tag: str, user_id: int) -> str:
        payload = {"Tag": tag, "AgreeUser": user_id}
        result = await self._request_alias("POST", "/agreeuser", json=payload)
        return result.content

    async def get_plate_json(self) -> dict[str, list[int]]:
        result = await self._request_alias("GET", "/maimaidxplate")
        if result.code == 0:
            return result.content
        raise ServerError("获取牌子数据失败")

