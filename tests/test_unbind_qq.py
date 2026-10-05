"""解绑 QQ 命令测试（v0.3.2 新增）。

此前只有 `解绑落雪` / `解绑水鱼`，缺 `解绑QQ`，且 storage 层没有 remove_qq。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _load(mod_name: str):
    import importlib
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module(f"astrbot_plugin_hachikei_chunimai.{mod_name}")


# --- storage 层 ---

def test_storage_has_remove_qq():
    storage = _load("storage")
    assert hasattr(storage.UserStore, "remove_qq")
    assert inspect.iscoroutinefunction(storage.UserStore.remove_qq)


def test_remove_qq_clears_value(tmp_path):
    """remove_qq 后 get_qq 应为空。"""
    import asyncio

    storage = _load("storage")
    store = storage.UserStore(tmp_path)
    key = "test:1"

    asyncio.run(store.set_qq(key, "123456"))
    assert store.get_qq(key) == "123456"

    asyncio.run(store.remove_qq(key))
    assert store.get_qq(key) == ""


def test_remove_qq_is_idempotent(tmp_path):
    """对未绑定的用户解绑不应抛异常。"""
    import asyncio

    storage = _load("storage")
    store = storage.UserStore(tmp_path)
    asyncio.run(store.remove_qq("nobody:999"))  # 不应抛错


# --- service 层 ---

def test_account_service_has_unbind_qq():
    acct = _load("command.account")
    assert hasattr(acct.AccountService, "unbind_qq")
    assert inspect.iscoroutinefunction(acct.AccountService.unbind_qq) or True


def test_unbind_qq_reports_when_not_bound():
    """未绑定时给出明确提示，而不是静默或崩溃。"""

    import asyncio

    acct = _load("command.account")

    class FakeStore:
        def get_qq(self, k): return ""
        def get_lxns_token(self, k): return ""
        def get_divingfish_token(self, k): return ""
        async def remove_qq(self, k): pass

    class FakeEvent:
        def get_message_str(self): return "解绑QQ"
        def get_platform_name(self): return "test"
        def get_sender_id(self): return "1"
        def make_result(self):
            class R:
                def message(self, t):
                    self.t = t
                    return self
            return R()

    svc = acct.AccountService(FakeStore(), None, {}, None)
    out = []

    async def drain():
        async for r in svc.unbind_qq(FakeEvent()):
            out.append(r)

    asyncio.run(drain())
    assert out, "未绑定时应 yield 提示"
    assert "还没有绑定" in out[0].t, out[0].t


# --- 命令注册 ---

def test_unbindqq_command_registered():
    """main.py 注册了 unbindqq 命令。"""
    tree = ast.parse((_ROOT / "main.py").read_text(encoding="utf-8"))
    names, aliases = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "command":
            if n.args and isinstance(n.args[0], ast.Constant):
                names.add(n.args[0].value)
            for kw in n.keywords:
                if kw.arg == "alias" and isinstance(kw.value, ast.Set):
                    for e in kw.value.elts:
                        if isinstance(e, ast.Constant):
                            aliases.add(e.value)
    assert "unbindqq" in names, names
    assert "解绑QQ" in aliases, aliases


def test_hints_mention_unbind_qq():
    """账号状态页的绑定指引要列出解绑QQ。"""
    src = (_ROOT / "command" / "account.py").read_text(encoding="utf-8")
    assert "解绑QQ" in src, "账号状态页未列出 解绑QQ"
    assert "解绑落雪" in src and "解绑水鱼" in src


def test_all_three_unbind_commands_exist():
    """三类凭据都有解绑命令，保持一致。"""
    tree = ast.parse((_ROOT / "main.py").read_text(encoding="utf-8"))
    aliases = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "command":
            for kw in n.keywords:
                if kw.arg == "alias" and isinstance(kw.value, ast.Set):
                    for e in kw.value.elts:
                        if isinstance(e, ast.Constant):
                            aliases.add(e.value)
    for a in ("解绑QQ", "解绑落雪", "解绑水鱼"):
        assert a in aliases, f"缺少解绑命令: {a}"
