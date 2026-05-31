"""用户数据和群配置的持久化存储。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UserRecord:
    rating: float = 0.0
    divingfish_import_token: str = ""
    bound_at: float = 0.0
    last_sync_at: float = 0.0
    last_sync_result: str = ""
    game_mode: str = ""  # 空=未设置，跟随群规则；非空=个人覆盖
    qq: str = ""  # 绑定的 QQ 号

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserRecord:
        return cls(
            rating=d.get("rating", 0.0) or 0.0,
            divingfish_import_token=d.get("divingfish_import_token", "") or "",
            bound_at=d.get("bound_at", 0.0) or 0.0,
            last_sync_at=d.get("last_sync_at", 0.0) or 0.0,
            last_sync_result=d.get("last_sync_result", "") or "",
            game_mode=d.get("game_mode", "") or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UserStore:
    """JSON 文件后端的用户数据存储。"""

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "users.json"
        self._lock = asyncio.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return
        try:
            self._data = json.loads(self._path.read_text("utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            logger.warning("用户数据文件损坏，已重置。")
            self._data = {}

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(path)

    async def save(self) -> None:
        await asyncio.to_thread(self._write_json, self._path, self._data)

    def get(self, user_key: str) -> UserRecord:
        d = self._data.get(user_key)
        return UserRecord.from_dict(d) if d else UserRecord()

    async def set_import_token(self, user_key: str, token: str) -> None:
        async with self._lock:
            rec = self._data.setdefault(user_key, {})
            rec["divingfish_import_token"] = token
            import time
            rec["bound_at"] = time.time()
            await self.save()

    async def set_sync_result(self, user_key: str, rating: float, result: str) -> None:
        async with self._lock:
            rec = self._data.setdefault(user_key, {})
            rec["rating"] = rating
            import time
            rec["last_sync_at"] = time.time()
            rec["last_sync_result"] = result
            await self.save()

    async def clear_local_profile(self, user_key: str, result: str) -> None:
        async with self._lock:
            rec = self._data.get(user_key)
            if rec:
                rec["rating"] = 0.0
                import time
                rec["last_sync_at"] = time.time()
                rec["last_sync_result"] = result
                await self.save()

    async def remove(self, user_key: str) -> bool:
        async with self._lock:
            if user_key in self._data:
                del self._data[user_key]
                await self.save()
                return True
            return False

    async def set_game_mode(self, user_key: str, game: str) -> None:
        """设置个人游戏模式。空字符串表示清除个人设置。"""
        async with self._lock:
            rec = self._data.setdefault(user_key, {})
            rec["game_mode"] = game
            await self.save()

    def get_game_mode(self, user_key: str) -> str:
        """获取个人游戏模式。空字符串表示未设置。"""
        d = self._data.get(user_key)
        if d:
            return d.get("game_mode", "") or ""
        return ""

    async def set_qq(self, user_key: str, qq: str) -> None:
        """绑定 QQ 号。"""
        async with self._lock:
            rec = self._data.setdefault(user_key, {})
            rec["qq"] = qq
            await self.save()

    def get_qq(self, user_key: str) -> str:
        """获取绑定的 QQ 号。"""
        d = self._data.get(user_key)
        if d:
            return d.get("qq", "") or ""
        return ""


class GroupConfigStore:
    """群级配置存储（猜歌开关、别名推送开关、禁用群列表等）。"""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir
        self._lock = asyncio.Lock()
        self._cache: dict[str, set[str]] = {}
        self._dir.mkdir(parents=True, exist_ok=True)

    def _file(self, name: str) -> Path:
        return self._dir / f"{name}.json"

    def _load_set(self, name: str) -> set[str]:
        if name in self._cache:
            return self._cache[name]
        f = self._file(name)
        try:
            data = json.loads(f.read_text("utf-8-sig"))
            s = set(data) if isinstance(data, list) else set()
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            s = set()
        self._cache[name] = s
        return s

    async def _save_set(self, name: str, s: set[str]) -> None:
        f = self._file(name)
        await asyncio.to_thread(
            UserStore._write_json, f, list(s)
        )

    def is_enabled(self, store_name: str, group_id: str) -> bool:
        """检查某个功能在指定群是否启用。"""
        disabled = self._load_set(store_name)
        return group_id not in disabled

    async def toggle(self, store_name: str, group_id: str, enable: bool) -> None:
        async with self._lock:
            s = self._load_set(store_name)
            if enable:
                s.discard(group_id)
            else:
                s.add(group_id)
            await self._save_set(store_name, s)

    def is_group_disabled(self, group_id: str) -> bool:
        return not self.is_enabled("disabled_groups", group_id)

    async def toggle_group(self, group_id: str, enable: bool) -> None:
        await self.toggle("disabled_groups", group_id, enable)

    def is_guess_enabled(self, group_id: str) -> bool:
        return self.is_enabled("disabled_guess", group_id)

    async def toggle_guess(self, group_id: str, enable: bool) -> None:
        await self.toggle("disabled_guess", group_id, enable)

    def is_alias_push_enabled(self, group_id: str) -> bool:
        return self.is_enabled("disabled_alias_push", group_id)

    async def toggle_alias_push(self, group_id: str, enable: bool) -> None:
        await self.toggle("disabled_alias_push", group_id, enable)

    # --- 游戏模式（群级） ---

    def get_group_game_mode(self, group_id: str) -> str:
        """获取群默认游戏模式。"""
        f = self._file("game_mode")
        try:
            data = json.loads(f.read_text("utf-8-sig"))
            return data.get(group_id, "maimai")
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return "maimai"

    async def set_group_game_mode(self, group_id: str, game: str) -> None:
        f = self._file("game_mode")
        try:
            data = json.loads(f.read_text("utf-8-sig"))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            data = {}
        data[group_id] = game
        await asyncio.to_thread(UserStore._write_json, f, data)

    # --- 查分器选择（群级） ---

    def get_prober(self, game: str, group_id: str | None = None) -> str:
        """获取查分器。返回 "divingfish" 或 "lxns"。"""
        # 个人设置
        if group_id:
            f = self._file("prober")
            try:
                data = json.loads(f.read_text("utf-8-sig"))
                key = f"{group_id}:{game}"
                if key in data:
                    return data[key]
            except (json.JSONDecodeError, OSError, FileNotFoundError):
                pass
        # 默认
        return "lxns" if game == "chunithm" else "divingfish"

    async def set_prober(self, game: str, prober: str, group_id: str | None = None) -> None:
        """设置查分器。"""
        f = self._file("prober")
        try:
            data = json.loads(f.read_text("utf-8-sig"))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            data = {}
        key = f"{group_id}:{game}" if group_id else f"global:{game}"
        data[key] = prober
        await asyncio.to_thread(UserStore._write_json, f, data)
