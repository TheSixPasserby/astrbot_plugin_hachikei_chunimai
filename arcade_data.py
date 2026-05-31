"""机厅数据管理。"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from .models import Arcade, ArcadeQueue

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ArcadeDataManager:
    """机厅数据和排队管理。"""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "arcade"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self.arcades: dict[str, Arcade] = {}
        self.queues: dict[str, ArcadeQueue] = {}
        self.subscriptions: dict[str, set[str]] = {}  # group_id -> {arcade_name, ...}
        self._load()

    def _file(self, name: str) -> Path:
        return self._dir / f"{name}.json"

    def _load_json(self, name: str) -> Any:
        f = self._file(name)
        try:
            return json.loads(f.read_text("utf-8"))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return None

    def _load(self) -> None:
        # 机厅列表
        data = self._load_json("arcades")
        if data:
            for k, v in data.items():
                self.arcades[k] = Arcade.model_validate(v)

        # 排队状态
        data = self._load_json("queues")
        if data:
            for k, v in data.items():
                self.queues[k] = ArcadeQueue.model_validate(v)

        # 订阅关系
        data = self._load_json("subscriptions")
        if data:
            for gid, names in data.items():
                self.subscriptions[gid] = set(names)

    async def _save(self, name: str, data: Any) -> None:
        f = self._file(name)
        await asyncio.to_thread(
            lambda: f.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        )

    async def save_all(self) -> None:
        async with self._lock:
            await self._save("arcades", {k: v.model_dump() for k, v in self.arcades.items()})
            await self._save("queues", {k: v.model_dump() for k, v in self.queues.items()})
            await self._save("subscriptions", {k: list(v) for k, v in self.subscriptions.items()})

    # --- 机厅 CRUD ---

    def find_arcade(self, keyword: str) -> Arcade | None:
        keyword_lower = keyword.lower()
        if keyword in self.arcades:
            return self.arcades[keyword]
        for name, arcade in self.arcades.items():
            if keyword_lower == name.lower():
                return arcade
            for alias in arcade.aliases:
                if keyword_lower == alias.lower():
                    return arcade
        for name, arcade in self.arcades.items():
            if keyword_lower in name.lower():
                return arcade
            for alias in arcade.aliases:
                if keyword_lower in alias.lower():
                    return arcade
        return None

    def search_arcades(self, keyword: str) -> list[Arcade]:
        keyword_lower = keyword.lower()
        results = []
        for name, arcade in self.arcades.items():
            if keyword_lower in name.lower():
                results.append(arcade)
                continue
            for alias in arcade.aliases:
                if keyword_lower in alias.lower():
                    results.append(arcade)
                    break
        return results

    async def add_arcade(self, name: str, address: str = "", machine_count: int = 0, aliases: list[str] | None = None) -> None:
        async with self._lock:
            self.arcades[name] = Arcade(name=name, address=address, machine_count=machine_count, aliases=aliases or [])
            await self.save_all()

    async def remove_arcade(self, name: str) -> bool:
        async with self._lock:
            arcade = self.find_arcade(name)
            if not arcade:
                return False
            del self.arcades[arcade.name]
            self.queues.pop(arcade.name, None)
            for subs in self.subscriptions.values():
                subs.discard(arcade.name)
            await self.save_all()
            return True

    async def modify_arcade(self, name: str, **kwargs: Any) -> bool:
        async with self._lock:
            arcade = self.find_arcade(name)
            if not arcade:
                return False
            for k, v in kwargs.items():
                if hasattr(arcade, k) and v is not None:
                    setattr(arcade, k, v)
            await self.save_all()
            return True

    async def add_arcade_alias(self, name: str, alias: str) -> bool:
        async with self._lock:
            arcade = self.find_arcade(name)
            if not arcade:
                return False
            if alias not in arcade.aliases:
                arcade.aliases.append(alias)
            await self.save_all()
            return True

    async def remove_arcade_alias(self, name: str, alias: str) -> bool:
        async with self._lock:
            arcade = self.find_arcade(name)
            if not arcade:
                return False
            if alias in arcade.aliases:
                arcade.aliases.remove(alias)
            await self.save_all()
            return True

    # --- 订阅 ---

    def get_subscriptions(self, group_id: str) -> list[str]:
        return list(self.subscriptions.get(group_id, set()))

    async def subscribe(self, group_id: str, arcade_name: str) -> bool:
        async with self._lock:
            arcade = self.find_arcade(arcade_name)
            if not arcade:
                return False
            subs = self.subscriptions.setdefault(group_id, set())
            subs.add(arcade.name)
            await self.save_all()
            return True

    async def unsubscribe(self, group_id: str, arcade_name: str) -> bool:
        async with self._lock:
            arcade = self.find_arcade(arcade_name)
            if not arcade:
                return False
            subs = self.subscriptions.get(group_id, set())
            subs.discard(arcade.name)
            await self.save_all()
            return True

    # --- 排队 ---

    async def update_queue(
        self, arcade_name: str, person_delta: int = 0, card_delta: int = 0,
        set_person: int | None = None, set_card: int | None = None,
        operator: str = "",
    ) -> ArcadeQueue | None:
        async with self._lock:
            arcade = self.find_arcade(arcade_name)
            if not arcade:
                return None
            queue = self.queues.get(arcade.name)
            if queue is None:
                queue = ArcadeQueue(arcade_name=arcade.name)
                self.queues[arcade.name] = queue

            if set_person is not None:
                queue.person_count = max(0, set_person)
            else:
                queue.person_count = max(0, queue.person_count + person_delta)

            if set_card is not None:
                queue.card_count = max(0, set_card)
            else:
                queue.card_count = max(0, queue.card_count + card_delta)

            queue.updated_by = operator
            queue.updated_at = time.time()
            await self.save_all()
            return queue

    def get_queue(self, arcade_name: str) -> ArcadeQueue | None:
        arcade = self.find_arcade(arcade_name)
        if not arcade:
            return None
        return self.queues.get(arcade.name)

    def get_queues_for_group(self, group_id: str) -> list[ArcadeQueue]:
        subs = self.subscriptions.get(group_id, set())
        return [self.queues[name] for name in subs if name in self.queues]
