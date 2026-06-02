"""SGWCMAID 二维码同步：从街机获取成绩并上传到查分器。"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)



# --- SGID 解析 ---

_SGID_PATTERN = re.compile(r"(SGWCMAID[^\s<>\]\[\"']+)", re.IGNORECASE)
_SGID_TS_PATTERN = re.compile(r"^SGWCMAID(\d{12})", re.IGNORECASE)
_CN_TZ = timezone(timedelta(hours=8))


def extract_sgid(text: str) -> str | None:
    """从消息文本中提取 SGID。"""
    m = _SGID_PATTERN.search(text)
    return m.group(1).upper() if m else None


def is_valid_sgid(sgid: str) -> bool:
    """验证 SGID 格式。"""
    return sgid.upper().startswith("SGWCMAID") and 12 <= len(sgid) <= 1024


def sgid_fresh(sgid: str, max_age: int = 180) -> bool:
    """验证 SGID 时间戳是否在有效期内。"""
    m = _SGID_TS_PATTERN.match(sgid)
    if not m:
        return False
    try:
        dt = datetime.strptime(f"20{m.group(1)}", "%Y%m%d%H%M%S").replace(tzinfo=_CN_TZ)
    except ValueError:
        return False
    now = datetime.now(_CN_TZ)
    age = (now - dt).total_seconds()
    return -60 <= age <= max_age


# --- 同步结果 ---

@dataclass
class SyncResult:
    player_name: str = ""
    rating: int = 0
    score_count: int = 0
    warning: str = ""


# --- 同步服务 ---

class QRSyncService:
    """SGWCMAID 二维码同步服务（基于 maimai-py）。"""

    def __init__(self, timeout: float = 30.0, proxy: str = "", df_dev_token: str = "") -> None:
        self._timeout = timeout
        self._proxy = proxy.strip() or None
        self._df_dev_token = df_dev_token.strip() or ""
        self._client: Any = None
        self._imports: dict[str, Any] | None = None
        self._used_sgids: dict[str, float] = {}

    def _load_imports(self) -> dict[str, Any]:
        if self._imports is not None:
            return self._imports
        try:
            from maimai_py import (
                ArcadeProvider,
                DivingFishProvider,
                LXNSProvider,
                MaimaiClient,
                PlayerIdentifier,
            )
            from maimai_py import exceptions as maimai_exceptions
        except ImportError as e:
            raise RuntimeError(
                "缺少 maimai-py 依赖，请安装：pip install maimai-py>=1.4.2"
            ) from e

        self._imports = {
            "ArcadeProvider": ArcadeProvider,
            "DivingFishProvider": DivingFishProvider,
            "LXNSProvider": LXNSProvider,
            "MaimaiClient": MaimaiClient,
            "PlayerIdentifier": PlayerIdentifier,
            "AimeServerError": getattr(maimai_exceptions, "AimeServerError", None),
            "TitleServerError": getattr(maimai_exceptions, "TitleServerError", None),
            "TitleServerBlockedError": getattr(maimai_exceptions, "TitleServerBlockedError", None),
            "TitleServerNetworkError": getattr(maimai_exceptions, "TitleServerNetworkError", None),
            "ArcadeError": getattr(maimai_exceptions, "ArcadeError", None),
            "ArcadeIdentifierError": getattr(maimai_exceptions, "ArcadeIdentifierError", None),
            "InvalidPlayerIdentifierError": getattr(maimai_exceptions, "InvalidPlayerIdentifierError", None),
            "PrivacyLimitationError": getattr(maimai_exceptions, "PrivacyLimitationError", None),
        }
        return self._imports

    @property
    def client(self) -> Any:
        imports = self._load_imports()
        if self._client is None:
            self._client = imports["MaimaiClient"](timeout=self._timeout)
        return self._client

    def _check_one_time(self, sgid: str) -> bool:
        """检查 SGID 是否已使用。返回 True 表示可用。"""
        now = time.time()
        expired = [k for k, v in self._used_sgids.items() if v < now]
        for k in expired:
            del self._used_sgids[k]
        digest = hashlib.sha256(sgid.encode()).hexdigest()
        if digest in self._used_sgids:
            return False
        self._used_sgids[digest] = now + 300
        return True

    def _arcade_provider(self) -> Any:
        try:
            return self._load_imports()["ArcadeProvider"](http_proxy=self._proxy)
        except TypeError:
            return self._load_imports()["ArcadeProvider"]()

    def _divingfish_provider(self) -> Any:
        try:
            return self._load_imports()["DivingFishProvider"](developer_token=self._df_dev_token)
        except TypeError:
            return self._load_imports()["DivingFishProvider"]()

    def _lxns_provider(self) -> Any:
        return self._load_imports()["LXNSProvider"]()

    def _identifier(self, **kwargs: Any) -> Any:
        return self._load_imports()["PlayerIdentifier"](**kwargs)

    # --- 公开方法 ---

    def validate_sgid(self, sgid: str) -> str | None:
        """验证 SGID，返回错误信息或 None（通过）。"""
        if not is_valid_sgid(sgid):
            return "无效的二维码格式。"
        if not sgid_fresh(sgid):
            return "二维码已过期（有效期 180 秒），请重新获取。"
        if not self._check_one_time(sgid):
            return "该二维码已被使用，请重新获取。"
        return None

    async def get_arcade_credentials(self, sgid: str) -> dict:
        """用 SGID 换取 arcade 凭证。返回 {"credentials": str, "player_name": str}。"""
        identifier = await self.client.qrcode(sgid, http_proxy=self._proxy)
        creds = getattr(identifier, "credentials", None)
        if not isinstance(creds, str) or not creds:
            raise RuntimeError("二维码返回的凭据格式异常。")

        return {"credentials": creds, "player_name": ""}

    async def sync_creds_to_divingfish(self, arcade_creds: str, import_token: str) -> SyncResult:
        """用缓存的凭证同步到水鱼。"""
        arcade_id = self._identifier(credentials=arcade_creds)
        scores = await self.client.scores(arcade_id, provider=self._arcade_provider())
        target_id = self._identifier(credentials=import_token)
        await self.client.updates(target_id, scores.scores, provider=self._divingfish_provider())

        # 从水鱼获取玩家名
        player_name = ""
        try:
            player = await self.client.players(target_id, provider=self._divingfish_provider())
            player_name = str(getattr(player, "name", "") or "")
        except Exception:
            pass

        return SyncResult(
            player_name=player_name,
            rating=getattr(scores, "rating", 0) or 0,
            score_count=len(scores.scores),
        )

    async def sync_creds_to_lxns(self, arcade_creds: str, access_token: str) -> SyncResult:
        """用缓存的凭证同步到落雪。"""
        arcade_id = self._identifier(credentials=arcade_creds)
        scores = await self.client.scores(arcade_id, provider=self._arcade_provider())
        target_id = self._identifier(credentials=access_token)
        await self.client.updates(target_id, scores.scores, provider=self._lxns_provider())

        # 从落雪获取玩家名
        player_name = ""
        try:
            player = await self.client.players(target_id, provider=self._lxns_provider())
            player_name = str(getattr(player, "name", "") or "")
        except Exception:
            pass

        return SyncResult(
            player_name=player_name,
            rating=getattr(scores, "rating", 0) or 0,
            score_count=len(scores.scores),
        )

    async def sync_to_divingfish(self, sgid: str, import_token: str) -> SyncResult:
        """用 SGID 直接同步到水鱼。"""
        creds = await self.get_arcade_credentials(sgid)
        return await self.sync_creds_to_divingfish(creds["credentials"], import_token)

    async def sync_to_lxns(self, sgid: str, access_token: str) -> SyncResult:
        """用 SGID 直接同步到落雪。"""
        creds = await self.get_arcade_credentials(sgid)
        return await self.sync_creds_to_lxns(creds["credentials"], access_token)

    async def close(self) -> None:
        if self._client:
            http_client = getattr(self._client, "_client", None)
            aclose = getattr(http_client, "aclose", None)
            if aclose:
                await aclose()
            self._client = None

    def describe_error(self, exc: BaseException) -> str:
        """将异常转换为用户友好的中文消息。"""
        imports = self._imports or {}
        checks = (
            ("AimeServerError", "二维码无效或已过期，请重新获取。"),
            ("TitleServerBlockedError", "舞萌标题服务器拒绝了请求，可能需要配置代理（http_proxy）或稍后再试。"),
            ("TitleServerNetworkError", "舞萌标题服务器网络请求失败，请稍后再试。"),
            ("TitleServerError", "舞萌标题服务器请求失败，请稍后再试。"),
            ("ArcadeIdentifierError", "二维码凭据无效或已过期，请重新获取。"),
            ("ArcadeError", "机台数据源返回异常，可能是二维码过期或服务波动。"),
            ("InvalidPlayerIdentifierError", "查分器 Token 无效，请重新绑定。"),
            ("PrivacyLimitationError", "查分器账号未允许第三方访问，请在查分器中开启权限。"),
        )
        for class_name, message in checks:
            cls = imports.get(class_name)
            if cls and isinstance(exc, cls):
                return message
        return f"操作失败：{exc}"
