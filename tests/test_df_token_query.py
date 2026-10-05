"""水鱼 token 查询 + 未绑定引导文案测试。"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


# --- api_client.query_user_b50 凭据优先级 ---

def _load_api():
    import importlib
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("astrbot_plugin_hachikei_chunimai.api_client")


def test_query_b50_accepts_token_param():
    api = _load_api()
    sig = inspect.signature(api.MaimaiAPI.query_user_b50)
    assert "token" in sig.parameters, sig


def test_query_b50_priority_token_over_qq():
    """token 优先于 qq（实测水鱼：token 在前时 qq 被忽略）。"""
    api = _load_api()

    captured = {}

    class FakeResp:
        status = 200

        async def json(self):
            return {
                "nickname": "n",
                "username": "u",
                "rating": 1,
                "additional_rating": 0,
                "charts": None,
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        closed = False

        def request(self, method, url, headers=None, proxy=None, **kw):
            captured.update(kw.get("json", {}))
            return FakeResp()

        async def close(self):
            pass

    api_inst = api.MaimaiAPI()
    api_inst._session = FakeSession()

    import asyncio

    asyncio.run(api_inst.query_user_b50(qqid=123, token="tok", username="u"))
    assert "token" in captured and captured["token"] == "tok", captured
    assert "qq" not in captured, captured
    assert "username" not in captured, captured


def test_query_b50_falls_back_to_qq_without_token():
    api = _load_api()
    captured = {}

    class FakeResp:
        status = 200

        async def json(self):
            return {
                "nickname": "n",
                "username": "u",
                "rating": 1,
                "additional_rating": 0,
                "charts": None,
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        closed = False

        def request(self, method, url, headers=None, proxy=None, **kw):
            captured.update(kw.get("json", {}))
            return FakeResp()

        async def close(self):
            pass

    api_inst = api.MaimaiAPI()
    api_inst._session = FakeSession()

    import asyncio

    asyncio.run(api_inst.query_user_b50(qqid=123))
    assert captured.get("qq") == 123, captured
    assert "token" not in captured, captured


def test_query_b50_raises_without_any_credential():
    """三种凭据都没有时应抛 UserNotFoundError，而不是发空请求。"""
    api = _load_api()
    from astrbot_plugin_hachikei_chunimai.errors import UserNotFoundError

    api_inst = api.MaimaiAPI()
    import asyncio

    with pytest.raises(UserNotFoundError):
        asyncio.run(api_inst.query_user_b50())


# --- main.py 接线 ---

def test_main_has_df_token_helper():
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "def _get_df_token" in src, "缺少 _get_df_token"


def test_main_has_bind_hint_with_commands():
    """未绑定提示必须包含可执行命令，而不是让用户手足无措。"""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "_BIND_HINT" in src
    for cmd in ("绑定QQ", "绑定水鱼", "绑定落雪", "绑定账号"):
        assert cmd in src, f"绑定指引缺少 {cmd}"


def test_no_undefined_df_token_in_any_function():
    """所有使用 df_token 的函数内必须先赋值（防 NameError）。"""
    tree = ast.parse((_ROOT / "main.py").read_text(encoding="utf-8"))
    bad = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        assigned = {
            n.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        for n in ast.walk(fn):
            if (
                isinstance(n, ast.Name)
                and n.id == "df_token"
                and isinstance(n.ctx, ast.Load)
                and n.id not in assigned
            ):
                bad.append((fn.name, n.lineno))
    assert not bad, f"df_token 未定义: {bad}"


def test_all_divingfish_handlers_receive_token():
    """水鱼 handler 调用点都应传 token。"""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    import re

    for h in (
        "mai_b50_handler",
        "mai_minfo_handler",
        "mai_ginfo_handler",
        "mai_plate_progress_handler",
        "mai_level_progress_handler",
        "mai_rise_score_handler",
    ):
        # 排除 lxns_ 前缀的落雪变体
        pattern = rf"(?<!lxns_)\b{h}\(event"
        for line in src.splitlines():
            if re.search(pattern, line) and "import" not in line:
                assert "token=" in line, f"{h} 未传 token: {line.strip()}"


def test_log_field_renamed_to_disambiguate():
    """日志字段改名，避免 has_token 被误读成水鱼 token。"""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "has_lxns_token=" in src
    assert "has_df_token=" in src
    assert "qq={qq}, has_token=" not in src


# --- 错误文案 ---

def test_error_messages_include_binding_commands():
    """用户类错误文案必须给出下一步命令。"""
    import re

    src = (_ROOT / "errors.py").read_text(encoding="utf-8")
    # 只检查 _ERROR_MESSAGES 映射表里的用户文案（类 docstring 不算）
    table = re.search(r"_ERROR_MESSAGES[^=]*=\s*\{(.*?)\n\}", src, re.S)
    assert table, "未找到 _ERROR_MESSAGES"
    body = table.group(1)
    assert "用户不存在。" not in body, "映射表仍在输出无指引的『用户不存在。』"
    for exc in ("UserNotExistsError", "UserNotFoundError", "TokenNotFoundError"):
        assert exc in body, exc
    assert body.count("绑定水鱼") >= 2, "错误文案缺少绑定指引"
