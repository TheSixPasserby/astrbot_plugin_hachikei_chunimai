"""本地预览帮助图渲染，无需启动 AstrBot。

用法：
    python tools/preview_render.py [输出路径]

默认输出到 ./help_preview.png。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让项目可被 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.help import render_help  # noqa: E402
from command.help import HELP_SECTIONS  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("help_preview.png")
    img = render_help(HELP_SECTIONS, current_game="maimai", group_game=None)
    img.convert("RGB").save(out)
    print(f"帮助图已生成：{out} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
