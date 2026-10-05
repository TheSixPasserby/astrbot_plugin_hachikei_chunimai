"""SGWCMAID 解析函数测试：extract_sgid / is_valid_sgid / sgid_fresh。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.qr_sync import extract_sgid, is_valid_sgid, sgid_fresh


def test_extract_sgid_basic():
    assert extract_sgid("SGWCMAID202610030000") == "SGWCMAID202610030000"


def test_extract_sgid_lowercase_normalized():
    assert extract_sgid("sgwcmaid202610030000") == "SGWCMAID202610030000"


def test_extract_sgid_from_surrounding_text():
    text = "这是我的二维码 SGWCMAID20261003120000 请查收"
    assert extract_sgid(text) == "SGWCMAID20261003120000"


def test_extract_sgid_no_match():
    assert extract_sgid("没有二维码") is None
    assert extract_sgid("") is None


def test_is_valid_sgid():
    assert is_valid_sgid("SGWCMAID202610030000") is True
    assert is_valid_sgid("sgwcmaid202610030000") is True
    assert is_valid_sgid("SGWCMAID") is False  # 太短
    assert is_valid_sgid("INVALID") is False


def test_sgid_fresh_now():
    # SGID 时间戳是 12 位 YYMMDDHHMMSS（代码 f"20{ts}" 补全为 %Y%m%d%H%M%S）
    from datetime import datetime, timezone, timedelta
    cn_tz = timezone(timedelta(hours=8))
    now = datetime.now(cn_tz)
    sgid = "SGWCMAID" + now.strftime("%y%m%d%H%M%S")
    assert sgid_fresh(sgid, max_age=180) is True


def test_sgid_fresh_expired():
    from datetime import datetime, timezone, timedelta
    cn_tz = timezone(timedelta(hours=8))
    old = datetime.now(cn_tz) - timedelta(minutes=30)
    sgid = "SGWCMAID" + old.strftime("%y%m%d%H%M%S")
    assert sgid_fresh(sgid, max_age=180) is False


def test_sgid_fresh_bad_format():
    assert sgid_fresh("SGWCMAID999999999999") is False  # 无效时间
    assert sgid_fresh("NOTSGID") is False
