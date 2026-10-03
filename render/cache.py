"""渲染缓存：按内容 hash 缓存图片，避免重复渲染。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


def _cache_dir() -> Path:
    return Path("static/cache")


def content_hash(*parts: str) -> str:
    """对渲染输入做稳定 hash。"""
    h = hashlib.md5()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()[:16]


def cache_path(key: str, suffix: str = "png") -> Path:
    return _cache_dir() / f"{key}.{suffix}"


def load_cached(key: str) -> Image.Image | None:
    p = cache_path(key)
    if p.exists():
        try:
            return Image.open(p).convert("RGBA")
        except OSError:
            return None
    return None


def save_cache(img: Image.Image, key: str) -> Path:
    d = _cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = cache_path(key)
    img.save(p)
    return p
