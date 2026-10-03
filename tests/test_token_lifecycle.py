"""Token 生命周期测试：expires_at 存储与「过期才刷新」语义。"""

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import UserStore


def _make_store() -> UserStore:
    d = Path(tempfile.mkdtemp(prefix="chu_user_"))
    return UserStore(d)


def test_set_and_get_token_with_expiry():
    async def _run():
        store = _make_store()
        await store.set_lxns_token("u1", "acc", "ref", expires_at=1234.5)
        assert store.get_lxns_token("u1") == "acc"
        assert store.get_lxns_refresh_token("u1") == "ref"
        assert store.get_lxns_expires_at("u1") == 1234.5

    asyncio.run(_run())


def test_expiry_defaults_to_zero():
    async def _run():
        store = _make_store()
        await store.set_lxns_token("u1", "acc", "ref")  # 不带 expires_at
        assert store.get_lxns_expires_at("u1") == 0.0

    asyncio.run(_run())


def test_expiry_unknown_returns_zero():
    async def _run():
        store = _make_store()
        assert store.get_lxns_expires_at("nobody") == 0.0

    asyncio.run(_run())


def test_should_refresh_decision():
    """模拟「过期才刷新」的判断逻辑（与 main._get_lxns_token 一致）。"""
    def should_refresh(expires_at: float, now: float) -> bool:
        if expires_at and now < expires_at - 60:
            return False  # 有效期内，直接复用
        return True

    now = time.time()
    # 未过期（还有 10 分钟）→ 不刷新
    assert should_refresh(now + 600, now) is False
    # 已过期 → 刷新
    assert should_refresh(now - 1, now) is True
    # 快过期（剩余 < 60s 缓冲）→ 刷新
    assert should_refresh(now + 30, now) is True
    # 未知（0）→ 刷新
    assert should_refresh(0.0, now) is True
