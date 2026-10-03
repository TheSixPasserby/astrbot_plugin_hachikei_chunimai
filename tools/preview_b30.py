"""本地预览 CHUNITHM B30 图片渲染，无需启动 AstrBot。

用法：
    python tools/preview_b30.py [输出路径]

默认输出到 ./b30_preview.png。
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
from astrbot_plugin_hachikei_chunimai.render.b30 import render_b30  # noqa: E402


def _mock_cover(color: tuple[int, int, int]) -> Image.Image:
    im = Image.new("RGB", (100, 100), color)
    d = ImageDraw.Draw(im)
    d.ellipse([20, 20, 80, 80], fill=(255, 255, 255))
    return im


def _make(mid: int, title: str, rating: float, *, clear: str = "absolute", fc: str = "fullcombo") -> UnifiedScore:
    return UnifiedScore(
        music_id=mid, title=title, level_index=3, level_label="MASTER",
        ds=13.5, rating=rating, score=1000000, clear=clear,
        full_combo=fc, full_chain="fullchain",
    )


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("b30_preview.png")

    bests = [_make(800 + i, f"中二曲目 {i}", 13.0 + i * 0.1) for i in range(1, 7)]
    selections = [_make(900 + i, f"选择曲 {i}", 12.5, clear="hard", fc="alljustice") for i in range(1, 4)]
    new_bests = [_make(1000 + i, f"新谱 {i}", 15.0, clear="catastrophy", fc="alljusticecritical") for i in range(1, 3)]

    covers = {s.music_id: _mock_cover((i * 31 % 200 + 55, i * 47 % 200 + 55, i * 53 % 200 + 55))
              for i, s in enumerate(bests + selections + new_bests)}

    img = render_b30("示例玩家", 16.78, [("Best 30", bests), ("Selection 10", selections), ("New Best 20", new_bests)], covers)
    img.convert("RGB").save(out)
    print(f"B30 图已生成：{out} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
