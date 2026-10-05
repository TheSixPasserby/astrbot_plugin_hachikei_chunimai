"""maimai-py 1.6.0 迁移回归测试。

1.6.0 移除了 DivingFishProvider 的 developer_token 参数，改用账号 OAuth
（client_id / client_secret）。本测试锁定迁移结果，防止回退。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _load_qr_sync():
    """导入 qr_sync（不依赖 AstrBot）。"""
    import importlib
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("astrbot_plugin_hachikei_chunimai.qr_sync")


maimai_py = pytest.importorskip("maimai_py", reason="maimai-py 未安装")


def test_requirements_pins_1_6_0():
    """requirements.txt 必须锁到 1.6.0+。"""
    req = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "maimai-py==1.6.0" in req, req


def test_no_developer_token_in_source():
    """源码中不得再出现 developer_token（1.6.0 已移除该参数）。"""
    offenders = []
    for f in list(_ROOT.glob("*.py")) + list(_ROOT.glob("command/*.py")):
        if "__pycache__" in str(f):
            continue
        text = f.read_text(encoding="utf-8")
        if "developer_token" in text:
            offenders.append(f.name)
    assert not offenders, f"仍引用 developer_token: {offenders}"


def test_df_dev_token_kwarg_removed():
    """QRSyncService 不再接受 df_dev_token 关键字参数。"""
    qs = _load_qr_sync()
    sig = inspect.signature(qs.QRSyncService.__init__)
    assert "df_dev_token" not in sig.parameters, sig
    assert "df_client_id" in sig.parameters
    assert "df_client_secret" in sig.parameters


def test_divingfish_provider_accepts_oauth_kwargs():
    """无 OAuth 凭据时应能无参构造（Import-Token 路径仍可用）。"""
    qs = _load_qr_sync()
    svc = qs.QRSyncService(timeout=5)
    provider = svc._divingfish_provider()
    assert provider is not None


def test_developer_token_removed_upstream():
    """上游 1.6.0 确实已移除 developer_token 参数。"""
    from maimai_py import DivingFishProvider

    params = inspect.signature(DivingFishProvider.__init__).parameters
    assert "developer_token" not in params, params


def test_new_exceptions_mapped_without_prior_import():
    """1.6.0 新增的两个异常要有中文提示——即使 _imports 尚未加载。

    describe_error 可能在任何 client 调用之前就被触发（如二维码阶段失败），
    此时不能退化成原始异常消息。
    """
    from maimai_py.exceptions import PlayerNotAuthorizedError, RateLimitError

    qs = _load_qr_sync()
    svc = qs.QRSyncService(timeout=5)
    assert svc._imports is None, "本测试要求 _imports 初始为 None"
    assert "授权" in svc.describe_error(PlayerNotAuthorizedError("x"))
    assert "超限" in svc.describe_error(RateLimitError("x"))


def test_player_identifier_supports_ref_sub():
    """PlayerIdentifier 新增 ref / sub 字段（OAuth 主体标识）。"""
    from maimai_py import PlayerIdentifier

    params = inspect.signature(PlayerIdentifier).parameters
    assert "ref" in params, params
    assert "sub" in params, params


def test_import_token_path_still_supported():
    """Import-Token 同步路径（credentials=token）必须仍可用。"""
    qs = _load_qr_sync()
    svc = qs.QRSyncService(timeout=5)
    ident = svc._identifier(credentials="dummy-import-token")
    assert getattr(ident, "credentials", None) == "dummy-import-token"


def test_conf_schema_has_oauth_keys():
    """配置 schema 提供 OAuth 凭据项。"""
    import json

    schema = json.loads((_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    assert "divingfish_client_id" in schema
    assert "divingfish_client_secret" in schema


def test_main_passes_oauth_kwargs():
    """main.py 构造 QRSyncService 时用新参数名。"""
    tree = ast.parse((_ROOT / "main.py").read_text(encoding="utf-8"))
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", "") == "QRSyncService"
    ]
    assert calls, "main.py 未调用 QRSyncService"
    kws = {k.arg for c in calls for k in c.keywords if k.arg}
    assert "df_client_id" in kws and "df_client_secret" in kws, kws
    assert "df_dev_token" not in kws, kws
