"""测试夹具：让仓库作为包被导入。"""

import sys
from pathlib import Path

# 仓库根目录（astrbot_plugin_hachikei_chunimai 包的父目录）
_ROOT = Path(__file__).resolve().parent.parent
_PARENT = _ROOT.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
