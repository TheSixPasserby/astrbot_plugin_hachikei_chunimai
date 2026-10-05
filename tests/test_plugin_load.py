"""插件加载冒烟测试：复现生产环境 `MaiChuPlugin` 实例化路径。

背景：commit 531ff7b（拆出 command/account.py）删除范围过大，把相邻的
`_get_lxns_token` 与 `_get_qq` 一并误删，但 main.py 内仍有 13 处调用，
导致插件在 AstrBot 加载阶段直接抛
`AttributeError: 'MaiChuPlugin' object has no attribute '_get_lxns_token'`。

纯函数测试无法覆盖此类「属性缺失」缺陷，因此这里用最小 AstrBot 桩件
真实 import main.py 并实例化插件。
"""

from __future__ import annotations

import ast
import inspect
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_PARENT = _ROOT.parent


def _install_astrbot_stubs() -> None:
    """注册最小可用的 astrbot.* 桩件，避免依赖真实 AstrBot 安装。"""
    if "astrbot.api" in sys.modules:
        return

    def _mod(name, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    class _Logger:
        def __getattr__(self, _name):
            return lambda *a, **k: None

    class MessageEventResult:
        def message(self, text):
            self.chain = text
            return self

    class AstrMessageEvent:
        pass

    class AstrBotConfig(dict):
        pass

    class Context:
        async def send_message(self, *a, **k):
            return None

    class Star:
        def __init__(self, context=None):
            self.context = context

    class StarTools:
        @staticmethod
        def get_data_dir(plugin_name=None):
            data_dir = Path(__file__).parent / "_tmp_data"
            data_dir.mkdir(parents=True, exist_ok=True)
            return data_dir

    def _identity_decorator(*a, **k):
        def deco(fn):
            return fn
        return deco

    class EventMessageType:
        ALL = "all"

    class At:
        def __init__(self, qq=""):
            self.qq = qq

    class Plain:
        def __init__(self, text=""):
            self.text = text

    _mod("astrbot")
    _mod("astrbot.api", AstrBotConfig=AstrBotConfig, logger=_Logger())
    _mod("astrbot.api.all", register=_identity_decorator)
    _mod(
        "astrbot.api.event",
        AstrMessageEvent=AstrMessageEvent,
        MessageEventResult=MessageEventResult,
        Chain=list,
        message=lambda *a, **k: [],
    )
    _mod(
        "astrbot.api.event.filter",
        EventMessageType=EventMessageType,
        command=_identity_decorator,
        event_message_type=_identity_decorator,
    )
    _mod("astrbot.api.star", Context=Context, Star=Star, StarTools=StarTools)
    _mod("astrbot.api.message_components", At=At, Plain=Plain)


@pytest.fixture(scope="module")
def plugin_cls():
    """import main.py 并返回 MaiChuPlugin 类（真实加载路径）。"""
    _install_astrbot_stubs()
    for p in (str(_PARENT), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)

    if "maimai_py" not in sys.modules:
        try:
            __import__("maimai_py")
        except Exception:
            sys.modules["maimai_py"] = types.ModuleType("maimai_py")

    import astrbot_plugin_hachikei_chunimai.main as main_mod

    return main_mod.MaiChuPlugin


@pytest.fixture
def plugin(plugin_cls):
    """真实实例化一次插件（崩溃就发生在这里）。"""
    from astrbot.api.star import Context

    return plugin_cls(Context(), {})


def test_plugin_constructs(plugin):
    """插件必须能实例化——生产崩溃点。"""
    assert plugin is not None


@pytest.mark.parametrize(
    "attr",
    [
        # 531ff7b 误删的两个方法
        "_get_lxns_token",
        "_get_qq",
        # 其余 main.py 内被调用的 self.* 工具方法
        "_user_key",
        "_group_id",
        "_resolve_game",
        "_is_admin",
        "_is_group_disabled",
        "_table_name",
        "_message",
    ],
)
def test_helper_methods_exist(plugin, attr):
    """防止再次出现「调用点还在、定义被误删」。"""
    assert hasattr(plugin, attr), f"MaiChuPlugin 缺少 {attr}"


def test_sync_service_gets_callable_lxns_token_getter(plugin):
    """SyncService 构造时拿到的必须是可调用的 bound method（崩溃根因）。"""
    assert callable(plugin.sync._get_lxns_token)
    assert plugin.sync._get_lxns_token.__self__ is plugin


def test_self_attributes_all_resolve(plugin):
    """兜底：main.py 中读取的 self.* 都要有定义（context 来自 Star 基类）。"""
    src = inspect.getsource(sys.modules["astrbot_plugin_hachikei_chunimai.main"])
    tree = ast.parse(src)
    cls = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "MaiChuPlugin"
    )

    defined = set()
    for n in ast.walk(cls):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)
                elif isinstance(t, ast.Attribute) and getattr(t.value, "id", "") == "self":
                    defined.add(t.attr)
        elif isinstance(n, ast.AnnAssign):
            if isinstance(n.target, ast.Name):
                defined.add(n.target.id)
            elif (
                isinstance(n.target, ast.Attribute)
                and getattr(n.target.value, "id", "") == "self"
            ):
                defined.add(n.target.attr)
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith)):
            for t in ast.walk(n.target):
                if isinstance(t, ast.Attribute) and getattr(t.value, "id", "") == "self":
                    defined.add(t.attr)

    used = {
        n.attr
        for n in ast.walk(cls)
        if isinstance(n, ast.Attribute)
        and getattr(n.value, "id", "") == "self"
        and isinstance(n.ctx, ast.Load)
    }

    missing = used - defined - {"context"}
    assert not missing, f"main.py 读取了未定义的 self 属性: {sorted(missing)}"
