"""凭据隔离回归测试：确保 lxns token 不再走共享可变状态。

背景：此前 LxnsAPI._user_token 是共享成员变量，main.py / mai_table.py 用
save/restore 模式临时改值，异步并发下存在跨用户凭据串线风险。
本次修复改为显式 access_token 传参，彻底移除 _user_token。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def test_no_user_token_shared_state():
    """全库不得再出现 _user_token 共享状态。"""
    offenders = []
    for f in list(_ROOT.glob("*.py")) + list(_ROOT.glob("command/*.py")):
        if "__pycache__" in str(f):
            continue
        text = f.read_text(encoding="utf-8")
        if "_user_token" in text:
            offenders.append(f.name)
    assert not offenders, f"仍引用 _user_token: {offenders}"


def test_lxns_user_get_accepts_access_token():
    """LxnsAPI._user_get 应接受 access_token 参数。"""
    import importlib
    import inspect
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    lxns = importlib.import_module("astrbot_plugin_hachikei_chunimai.lxns_client")
    sig = inspect.signature(lxns.LxnsAPI._user_get)
    assert "access_token" in sig.parameters, sig


def test_lxns_has_no_user_token_attr():
    """LxnsAPI 不应再有 _user_token 实例属性。"""
    import importlib
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    lxns = importlib.import_module("astrbot_plugin_hachikei_chunimai.lxns_client")
    src = lxns.__file__
    tree = ast.parse(Path(src).read_text(encoding="utf-8"))
    # __init__ 里不应赋值 self._user_token
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Attribute) and getattr(t.value, "id", "") == "self" and t.attr == "_user_token":
                    pytest.fail("LxnsAPI.__init__ 仍赋值 self._user_token")


def test_handlers_receive_lxns_token_param():
    """落雪 handler 应显式接收 lxns_token 参数。"""
    import ast as _ast

    target_handlers = {
        "command/chu_score.py": ("chu_b30_handler", "chu_minfo_handler"),
        "command/mai_score.py": ("lxns_mai_b50_handler", "lxns_mai_minfo_handler"),
        "command/mai_table.py": ("mai_rise_score_handler",),
    }
    for fname, names in target_handlers.items():
        src = (_ROOT / fname).read_text(encoding="utf-8")
        tree = _ast.parse(src)
        found = {}
        for n in ast.walk(tree):
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and n.name in names:
                found[n.name] = [a.arg for a in n.args.args + n.args.kwonlyargs]
        for name in names:
            assert name in found, f"{fname} 缺少 {name}"
            assert "lxns_token" in found[name], f"{fname}.{name} 缺少 lxns_token 参数: {found[name]}"


def test_main_has_no_save_restore():
    """main.py 不再有 save/restore 临时改 token 的模式。"""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "saved_token" not in src
    assert "saved" not in src.split("lxns")[0] if "saved" in src else True
