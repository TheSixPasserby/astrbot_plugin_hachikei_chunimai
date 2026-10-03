"""CoverCache 封面缓存测试（不真正联网）。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.cover import CoverCache


def _make_cache(tmp_path, fetch_ok=True):
    cache = CoverCache(tmp_path, concurrency=2, timeout=3)

    async def _fake_fetch(url):
        if fetch_ok:
            from io import BytesIO
            from PIL import Image
            buf = BytesIO()
            Image.new("RGB", (10, 10), (255, 0, 0)).save(buf, "PNG")
            return buf.getvalue()
        return None

    cache._fetch = _fake_fetch
    return cache


def test_get_downloads_and_caches(tmp_path):
    cache = _make_cache(tmp_path)
    img = asyncio.run(cache.get(1234))
    assert img.size == (10, 10)
    # 永久缓存已写入
    assert cache.path(1234).exists()


def test_get_returns_placeholder_on_failure(tmp_path):
    cache = _make_cache(tmp_path, fetch_ok=False)
    img = asyncio.run(cache.get(9999))
    assert img.size == (200, 200)  # 占位图


def test_get_many_preserves_order(tmp_path):
    cache = _make_cache(tmp_path)
    ids = [100, 200, 300, 400, 500]
    imgs = asyncio.run(cache.get_many(ids))
    assert len(imgs) == 5
    # 每个都缓存了
    for mid in ids:
        assert cache.path(mid).exists()


def test_candidate_urls_dx_fallback(tmp_path):
    cache = _make_cache(tmp_path)
    urls = cache._candidate_urls(10123)
    assert urls[0] == "https://www.diving-fish.com/covers/10123.png"
    assert urls[1] == "https://www.diving-fish.com/covers/123.png"
    # 无 lxns 时只有两个候选
    assert len(urls) == 2


def test_candidate_urls_std(tmp_path):
    cache = _make_cache(tmp_path)
    urls = cache._candidate_urls(834)
    assert urls == ["https://www.diving-fish.com/covers/834.png"]


def test_chunithm_candidate_urls(tmp_path):
    cache = CoverCache(tmp_path, game="chunithm")
    urls = cache._candidate_urls(800)
    assert urls == ["https://assets2.lxns.net/chunithm/jacket/800.png"]
