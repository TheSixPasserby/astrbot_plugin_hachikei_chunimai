"""封面缓存：只缓存歌曲封面（永久），不缓存用户 B50/B30 成绩。

并发限制用 ``asyncio.Semaphore``，单个封面失败不影响整体，
失败时返回灰色占位图。支持 DX/SD ID fallback 与代理配置。
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

    封面以 DivingFish 5 位 ID 为本地文件名（``<df_id>.png``），
    与现有 ``music_picture_path`` / 猜歌代码的 ``static/cover`` 约定一致。
    """

    def __init__(
        self,
        cover_dir: Path,
        *,
        lxns: "LxnsAPI | None" = None,
        concurrency: int = 8,
        timeout: int = 15,
        http_proxy: str | None = None,
    ) -> None:
        self.cover_dir = Path(cover_dir)
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        self._lxns = lxns
        self._semaphore = asyncio.Semaphore(concurrency)
        self._timeout = timeout
        self._proxy = http_proxy

    def path(self, df_id: int) -> Path:
        return self.cover_dir / f"{df_id}.png"

    async def get(self, df_id: int) -> Image.Image:
        """获取封面（本地优先，缺失时下载）。失败返回占位图，绝不抛异常。"""
        p = self.path(df_id)
        if p.exists():
            try:
                return Image.open(p).convert("RGBA")
            except OSError:
                pass
        try:
            await self.download(df_id)
            if p.exists():
                return Image.open(p).convert("RGBA")
        except Exception as e:
            logger.warning(f"封面下载失败 ({df_id}): {e}")
        return _placeholder()

    async def get_many(self, df_ids: list[int]) -> list[Image.Image]:
        """并发获取多个封面，顺序与输入一致。"""
        async def _one(i: int, mid: int) -> tuple[int, Image.Image]:
            return i, await self.get(mid)

        results = await asyncio.gather(*(_one(i, mid) for i, mid in enumerate(df_ids)))
        results.sort(key=lambda t: t[0])
        return [img for _, img in results]

    async def download(self, df_id: int) -> Path:
        """下载封面到本地缓存。返回路径，失败抛异常。"""
        async with self._semaphore:
            p = self.path(df_id)
            if p.exists():
                return p

            for url in self._candidate_urls(df_id):
                try:
                    data = await self._fetch(url)
                except Exception:
                    continue
                if data:
                    # 封面统一用 DivingFish 5 位 ID 命名
                    await asyncio.to_thread(p.write_bytes, data)
                    return p
            raise RuntimeError(f"封面下载失败: {df_id}")

    def _candidate_urls(self, df_id: int) -> list[str]:
        """封面 URL 候选（DX/SD ID fallback + 多数据源）。

        依次尝试：
        1. DivingFish 完整 ID
        2. DivingFish 减 10000 的 ID（DX 曲目封面常位于短 ID）
        3. Lxns jacket（若配置了 Lxns 客户端）

        与 ``image_utils.music_picture_path`` 的 fallback 逻辑保持一致。
        """
        urls = [f"https://www.diving-fish.com/covers/{df_id}.png"]
        if df_id >= 10000:
            urls.append(f"https://www.diving-fish.com/covers/{df_id - 10000}.png")
        if self._lxns is not None:
            from .unified import df_id_to_lxns
            urls.append(self._lxns.mai_jacket_url(df_id_to_lxns(df_id)))
        return urls

    async def _fetch(self, url: str) -> bytes | None:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=self._proxy is None) as session:
            async with session.get(url, proxy=self._proxy) as res:
                if res.status == 200:
                    return await res.read()
                return None
