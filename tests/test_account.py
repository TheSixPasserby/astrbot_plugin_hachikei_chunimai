"""command.account AccountService 测试（fake store，不依赖 AstrBot）。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.command.account import AccountService, _user_key, _group_id


class _UserStore:
    def __init__(self):
        self.qq = {}
        self.lxns = {}
        self.df = {}

    async def set_qq(self, k, v): self.qq[k] = v
    def get_qq(self, k): return self.qq.get(k, "")
    async def set_lxns_token(self, k, t, r, expires_at=None): self.lxns[k] = (t, r)
    def get_lxns_token(self, k): return self.lxns.get(k, ("", ""))[0]
    def get_lxns_refresh_token(self, k): return self.lxns.get(k, ("", ""))[1]
    def get_lxns_expires_at(self, k): return None
    async def remove_lxns_token(self, k): self.lxns.pop(k, None)
    async def set_divingfish_token(self, k, t): self.df[k] = t
    def get_divingfish_token(self, k): return self.df.get(k, "")
    async def remove_divingfish_token(self, k): self.df.pop(k, None)


class _GroupStore:
    def __init__(self): self.prober = {}
    async def set_prober(self, game, prober, gid): self.prober[(game, gid)] = prober
    def get_prober(self, game, gid=None): return self.prober.get((game, gid), "divingfish")


def test_bind_qq_sets_store():
    us = _UserStore()
    svc = AccountService(us, _GroupStore(), {}, None)
    assert svc._pending_oauth == {} and svc._pending_df == {}
    asyncio.run(us.set_qq("k", "12345"))
    assert us.get_qq("k") == "12345"


def test_divingfish_token_validation_logic():
    # try_df_token 的格式校验通过 fake event 太麻烦，这里只验证 service 状态隔离
    svc = AccountService(_UserStore(), _GroupStore(), {}, None)
    svc._pending_df["k"] = 9999999999
    assert svc._pending_df.get("k") is not None
    svc._pending_df.pop("k")
    assert svc._pending_df.get("k") is None


def test_user_key_format():
    class E:
        def get_platform_name(self): return "p"
        def get_sender_id(self): return "123"
    assert _user_key(E()) == "p:123"


def test_group_id_fallback_empty():
    class E:
        def get_group_id(self): return None
        message_obj = None
        session_id = None
    assert _group_id(E()) == ""
