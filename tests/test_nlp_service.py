"""NlpService 自然语言路由的回归测试。"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def test_nlp_service_exists():
    import importlib
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    nlp = importlib.import_module("astrbot_plugin_hachikei_chunimai.command.nlp")
    assert hasattr(nlp, "NlpService")
    assert callable(nlp.NlpService.handle) or inspect.iscoroutinefunction(nlp.NlpService.handle)


def test_nlp_handle_is_async_generator():
    """handle 必须是 async generator（用 yield 产出结果）。"""
    import importlib
    import sys
    import asyncio

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    nlp = importlib.import_module("astrbot_plugin_hachikei_chunimai.command.nlp")

    async def _run():
        # 构造一个最小 NlpService，仅验证 handle 是 async generator
        svc = nlp.NlpService(
            api=None, lxns=None, music_data=None, chu_data=None,
            is_group_disabled=lambda e: True,   # 直接短路返回
            resolve_game=lambda e: "maimai",
            get_qq=lambda e: None,
            get_df_token=lambda e: "",
            get_lxns_token=lambda e: "",
            get_prober=lambda e, g: "divingfish",
            user_key_of=lambda e: "k",
            message=lambda e, t: t,
        )
        result = svc.handle(None)
        assert hasattr(result, "__aiter__"), "handle 应返回 async generator"
        # 群被禁用时应立即返回，无任何产出
        items = []
        async for r in result:
            items.append(r)
        assert items == []

    asyncio.run(_run())


def test_main_instantiates_nlp():
    """main.py 应在 __init__ 里挂载 self.nlp。"""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "self.nlp = NlpService(" in src, "main.py 未初始化 NlpService"
    assert "self.nlp.handle(event)" in src, "_on_message 未委托给 nlp.handle"


def test_nlp_file_is_self_contained():
    """nlp.py 不应再被 main.py 重复实现路由逻辑（main 只保留 pending 监听）。"""
    main_src = (_ROOT / "main.py").read_text(encoding="utf-8")
    # 自然语言路由的正则不应该再出现在 main.py 里
    for pattern in ("X的Y是多少分", "今日mai", "mai.*什么", "定数表$", "我要在"):
        assert pattern not in main_src, f"main.py 仍含路由正则: {pattern}"
