"""封面缓存：只缓存歌曲封面（永久），不缓存用户 B50/B30 成绩。

并发限制用 ``asyncio.Semaphore``，单个封面失败不影响整体，
失败时返回灰色占位图。支持 maimai / CHUNITHM 两种封面源与代理配置。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .lxns_client import LxnsAPI

_DEFAULT_PLACEHOLDER: Image.Image | None = None


def _placeholder(size: int = 200) -> Image.Image:
    """灰色占位图（覆盖下载失败 / 本地缺失场景）。"""
    global _DEFAULT_PLACEHOLDER
    if _DEFAULT_PLACEHOLDER is None:
        _DEFAULT_PLACEHOLDER = Image.new("RGB", (size, size), (180, 180, 180))
    return _DEFAULT_PLACEHOLDER


class CoverCache:
    """封面下载 + 永久本地缓存。

    - ``game="maimai"``：DivingFish 5 位 ID 封面（``static/cover``，兼容既有代码）。
    - ``game="chunithm"``：Lxns CHUNITHM jacket（4 位 ID，``static/cover_chu``）。
    """

    def __init__(
        self,
        cover_dir: Path,
        *,
        game: str = "maimai",
        lxns: "LxnsAPI | None" = None,
        concurrency: int = 8,
        timeout: int = 15,
        http_proxy: str | None = None,
    ) -> None:
        self.game = game if game in ("maimai", "chunithm") else "maimai"
        self.cover_dir = Path(cover_dir)
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        self._lxns = lxns
        self._semaphore = asyncio.Semaphore(concurrency)
        self._timeout = timeout
        self._proxy = http_proxy

    def path(self, song_id: int) -> Path:
        return self.cover_dir / f"{song_id}.png"

    async def get(self, song_id: int) -> Image.Image:
        """获取封面（本地优先，缺失时下载）。失败返回占位图，绝不抛异常。"""
        p = self.path(song_id)
        if p.exists():
            try:
                return Image.open(p).convert("RGBA")
            except OSError:
                pass
        try:
            await self.download(song_id)
            if p.exists():
                return Image.open(p).convert("RGBA")
        except Exception as e:
            logger.warning(f"封面下载失败 ({song_id}): {e}")
        return _placeholder()

    async def get_many(self, song_ids: list[int]) -> list[Image.Image]:
        """并发获取多个封面，顺序与输入一致。"""
        async def _one(i: int, mid: int) -> tuple[int, Image.Image]:
            return i, await self.get(mid)

        results = await asyncio.gather(*(_one(i, mid) for i, mid in enumerate(song_ids)))
        results.sort(key=lambda t: t[0])
        return [img for _, img in results]

    async def download(self, song_id: int) -> Path:
        """下载封面到本地缓存。返回路径，失败抛异常。"""
        async with self._semaphore:
            p = self.path(song_id)
            if p.exists():
                return p

            for url in self._candidate_urls(song_id):
                try:
                    data = await self._fetch(url)
                except Exception:
                    continue
                if data:
                    await asyncio.to_thread(p.write_bytes, data)
                    return p
            raise RuntimeError(f"封面下载失败: {song_id}")

    def _candidate_urls(self, song_id: int) -> list[str]:
        """封面 URL 候选（按 game 区分数据源与 ID fallback）。"""
        if self.game == "chunithm":
            if self._lxns is not None:
                return [self._lxns.chu_jacket_url(song_id)]
            return [f"{'https://assets2.lxns.net/chunithm'}/jacket/{song_id}.png"]

        # maimai：DivingFish 完整 ID → 减 10000（DX 曲目封面常位于短 ID）→ Lxns jacket
        urls = [f"https://www.diving-fish.com/covers/{song_id}.png"]
        if song_id >= 10000:
            urls.append(f"https://www.diving-fish.com/covers/{song_id - 10000}.png")
        if self._lxns is not None:
            from .unified import df_id_to_lxns
            urls.append(self._lxns.mai_jacket_url(df_id_to_lxns(song_id)))
        return urls

    async def _fetch(self, url: str) -> bytes | None:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=self._proxy is None) as session:
            async with session.get(url, proxy=self._proxy) as res:
                if res.status == 200:
                    return await res.read()
                return None
