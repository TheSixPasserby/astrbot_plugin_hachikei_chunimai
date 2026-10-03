"""make_proxy 纯函数测试（无外部依赖）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.utils import make_proxy  # noqa: E402


def test_none_returns_none():
    assert make_proxy(None) is None


def test_empty_string_returns_none():
    assert make_proxy("") is None


def test_whitespace_returns_none():
    assert make_proxy("   \n\t") is None


def test_host_port_gets_http_prefix():
    assert make_proxy("127.0.0.1:7890") == "http://127.0.0.1:7890"


def test_bare_host_gets_http_prefix():
    assert make_proxy("proxy.local:8080") == "http://proxy.local:8080"


def test_existing_scheme_preserved():
    assert make_proxy("http://127.0.0.1:7890") == "http://127.0.0.1:7890"
    assert make_proxy("https://proxy.example.com") == "https://proxy.example.com"


def test_scheme_normalized_to_http():
    # 已含 scheme 的地址（含 socks5://）原样保留，不做改动
    assert make_proxy("socks5://127.0.0.1:1080") == "socks5://127.0.0.1:1080"


def test_leading_trailing_space_trimmed():
    assert make_proxy("  127.0.0.1:7890  ") == "http://127.0.0.1:7890"
