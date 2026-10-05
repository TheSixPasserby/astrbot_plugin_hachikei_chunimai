"""command.sync SyncService 测试（不依赖 AstrBot / maimai-py）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.command.sync import SyncService


class _UserStore:
    def __init__(self): self.df = {}
    def get_divingfish_token(self, k): return self.df.get(k, "")


def _make_svc():
    return SyncService(
        user_store=_UserStore(),
        get_qr_sync=lambda: None,
        get_lxns_token=_async_return_empty,
        user_key_of=lambda e: "u1",
        message=lambda e, t: t,
    )


async def _async_return_empty(event):
    return ""


def test_initial_state():
    svc = _make_svc()
    assert svc._pending_sync == {}
    assert svc.qr_sync is None
    assert not svc.has_pending("u1")


def test_has_pending():
    svc = _make_svc()
    svc._pending_sync["u1"] = ("lxns", 9999999999)
    assert svc.has_pending("u1")
    assert not svc.has_pending("u2")


def test_try_sync_sgid_no_qr_service():
    import asyncio
    svc = _make_svc()
    svc._pending_sync["u1"] = ("lxns", 9999999999)

    class E:
        def get_message_str(self): return "SGWCMAID1234567890"

    out = list(asyncio.run(_collect(svc.try_sync_sgid(E()))))
    # qr_sync 为 None → 提示未初始化
    assert any("未初始化" in m for m in out)


async def _collect(agen):
    return [x async for x in agen]
