"""别名推送 session 映射存储测试（纯逻辑，无需 AstrBot/PIL）。"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import GroupConfigStore


def _make_store() -> GroupConfigStore:
    d = Path(tempfile.mkdtemp(prefix="chu_push_"))
    return GroupConfigStore(d)


def test_session_set_get_and_remove():
    async def _run():
        store = _make_store()
        await store.set_and_save_alias_push_session("g1", "aiocqhttp:group:100")
        await store.set_and_save_alias_push_session("g2", "aiocqhttp:group:200")

        all_sessions = store.get_all_alias_push_sessions()
        assert all_sessions["g1"] == "aiocqhttp:group:100"
        assert all_sessions["g2"] == "aiocqhttp:group:200"

        await store.remove_alias_push_session("g1")
        assert "g1" not in store.get_all_alias_push_sessions()
        assert "g2" in store.get_all_alias_push_sessions()

    asyncio.run(_run())


def test_empty_by_default():
    async def _run():
        store = _make_store()
        assert store.get_all_alias_push_sessions() == {}

    asyncio.run(_run())
