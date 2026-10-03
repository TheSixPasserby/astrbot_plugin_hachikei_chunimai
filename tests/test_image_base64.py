"""image_to_base64 返回原始 base64（不含 base64:// 前缀）测试。"""

import base64
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.image_utils import image_to_base64


def test_returns_raw_base64_without_prefix():
    # 构造一个 1x1 图片
    from PIL import Image
    img = Image.new("RGB", (1, 1), (255, 0, 0))
    out = image_to_base64(img)
    assert not out.startswith("base64://"), f"不应带前缀，实际: {out[:20]}"
    # 能 base64 解码回字节
    decoded = base64.b64decode(out)
    assert len(decoded) > 0
    # 是合法 PNG 头
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"
