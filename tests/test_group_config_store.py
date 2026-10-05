"""GroupConfigStore 并发安全测试（无需 astrbot，需 aiofiles/aiodns 缺失时仍可跑纯逻辑）。

验证：多个群并发 read-modify-write 不互相覆盖。
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.storage import GroupConfigStore


def _make_store() -> GroupConfigStore:
    d = Path(tempfile.mkdtemp(prefix="chu_store_"))
    return GroupConfigStore(d)


def test_set_group_game_mode_concurrent():
    async def _run():
        store = _make_store()
        # 并发给 50 个群设置不同游戏
        await asyncio.gather(*[
            store.set_group_game_mode(f"g{i}", "chunithm" if i % 2 == 0 else "maimai")
            for i in range(50)
        ])
        # 全部读回，验证无覆盖
        for i in range(50):
            expect = "chunithm" if i % 2 == 0 else "maimai"
            assert store.get_group_game_mode(f"g{i}") == expect, f"g{i} 被覆盖"
        # 未设置的群回默认
        assert store.get_group_game_mode("not_exist") == "maimai"

    asyncio.run(_run())


def test_set_prober_concurrent():
    async def _run():
        store = _make_store()
        await asyncio.gather(*[
            store.set_prober("maimai", "divingfish" if i % 2 == 0 else "lxns", f"g{i}")
            for i in range(50)
        ])
        for i in range(50):
            expect = "divingfish" if i % 2 == 0 else "lxns"
            assert store.get_prober("maimai", f"g{i}") == expect, f"g{i} prober 被覆盖"
        # 全局默认
        assert store.get_prober("maimai", "unset") == "divingfish"
        assert store.get_prober("chunithm", "unset") == "lxns"

    asyncio.run(_run())


def test_global_prober():
    async def _run():
        store = _make_store()
        await store.set_prober("maimai", "lxns", None)
        # 全局 key 存在但 group 查询不回退到全局（保持原语义：group 无则默认）
        assert store.get_prober("maimai", "somegroup") == "divingfish"

    asyncio.run(_run())
