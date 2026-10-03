"""本地预览 B50 图片渲染，无需启动 AstrBot。

用法：
    python tools/preview_b50.py [输出路径]

默认输出到 ./b50_preview.png。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让项目作为包被导入（与测试 conftest 一致）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_ROOT.parent))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from astrbot_plugin_hachikei_chunimai.unified import UnifiedScore  # noqa: E402
from astrbot_plugin_hachikei_chunimai.render.b50 import render_b50  # noqa: E402


def _mock_cover(color: tuple[int, int, int]) -> Image.Image:
    im = Image.new("RGB", (100, 100), color)
    d = ImageDraw.Draw(im)
    d.ellipse([20, 20, 80, 80], fill=(255, 255, 255))
    return im


def _make(mid: int, title: str, rating: float, *, dx: bool = False) -> UnifiedScore:
    return UnifiedScore(
        music_id=mid, title=title, level_index=4 if dx else 3,
        level_label="RE:MASTER" if dx else "MASTER",
        ds=14.2 if dx else 13.4, rating=rating,
        type="dx" if dx else "sd",
        achievements=100.5 if dx else 99.5,
        dx_score=5000 if dx else 2000,
        rate="sssp" if dx else "ssp", fc="fcp" if dx else "fc", fs="",
    )


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("b50_preview.png")

    sd = [_make(10000 + i, f"标准曲目 {i}", 13.0 + i * 0.1) for i in range(1, 9)]
    dx = [_make(11000 + i, f"DX 曲目 {i}", 15.0, dx=True) for i in range(1, 5)]

    covers = {s.music_id: _mock_cover((i * 31 % 200 + 55, i * 47 % 200 + 55, i * 53 % 200 + 55))
              for i, s in enumerate(sd + dx)}

    img = render_b50("示例玩家", 15234, [("SD Best 35", sd), ("DX Best 15", dx)], covers)
    img.convert("RGB").save(out)
    print(f"B50 图已生成：{out} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
