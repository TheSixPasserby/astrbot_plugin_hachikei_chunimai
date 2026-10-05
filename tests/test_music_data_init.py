"""MusicDataManager 初始化完整性回归测试。

背景：加 property 时误把 __init__ 的初始化代码（guess_manager 等）
缩进到了 data_dir property 体内，导致 __init__ 提前结束，实例缺少
guess_manager / music_list / chart_stats 等核心属性，插件运行时崩
AttributeError。此测试锁定这些属性必须在 __init__ 正确初始化。
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def manager(tmp_path):
    import importlib
    import sys

    for p in (str(_ROOT.parent), str(_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    md = importlib.import_module("astrbot_plugin_hachikei_chunimai.mai_data")

    class FakeAPI:
        pass

    return md.MusicDataManager(FakeAPI(), tmp_path)


@pytest.mark.parametrize(
    "attr",
    [
        "api",
        "music_list",
        "chart_stats",
        "alias_list",
        "plate_data",
        "level_data",
        "guess_data",
        "guess_manager",
    ],
)
def test_init_attributes_exist(manager, attr):
    assert hasattr(manager, attr), f"MusicDataManager 缺少 {attr}"


def test_cover_dir_is_path(manager):
    assert isinstance(manager.cover_dir, Path)


def test_lxns_defaults_none(manager):
    assert manager.lxns is None


def test_data_dir_matches_input(manager, tmp_path):
    assert manager.data_dir == tmp_path


def test_init_does_not_stop_early():
    """确保 __init__ 的初始化语句没有被塞进 property 里。

    用 AST 检查：__init__ 里应包含所有核心属性的赋值，
    且 property 体内不应含 self.<attr> = 的赋值语句。
    """
    import ast
    import sys

    sys.path.insert(0, str(_ROOT))
    import astrbot_plugin_hachikei_chunimai.mai_data as md

    tree = ast.parse(Path(md.__file__).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MusicDataManager")

    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    init_attrs = set()
    for n in ast.walk(init):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Attribute) and getattr(t.value, "id", "") == "self":
                    init_attrs.add(t.attr)
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Attribute) and getattr(n.target.value, "id", "") == "self":
            init_attrs.add(n.target.attr)

    required = {"api", "music_list", "chart_stats", "alias_list", "plate_data", "level_data", "guess_data", "guess_manager"}
    missing = required - init_attrs
    assert not missing, f"__init__ 缺少初始化: {missing}"

    # property 体内不应有 self.X = 赋值
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name in ("cover_dir", "lxns", "data_dir"):
            for sub in ast.walk(n):
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Attribute) and getattr(t.value, "id", "") == "self":
                            pytest.fail(f"property {n.name} 内含 self.{t.attr} 赋值")
