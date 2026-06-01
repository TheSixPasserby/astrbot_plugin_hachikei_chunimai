"""通用工具函数。"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# --- 评级/连击格式化 ---

def fmt_fc(fs: str | None) -> str:
    """格式化 FC/FS 标签：fcp -> FC+, app -> AP+, fsdp -> FDX+ 等。"""
    if not fs:
        return "-"
    mapping = {
        "app": "AP+", "ap": "AP", "fcp": "FC+", "fc": "FC",
        "fsdp": "FDX+", "fsd": "FDX", "fsp": "FS+", "fs": "FS", "sync": "SYNC",
    }
    return mapping.get(fs.lower(), fs.upper())


def fmt_rate(rate: str | None) -> str:
    """格式化评级标签：sssp -> SSS+ 等。"""
    if not rate:
        return "-"
    mapping = {
        "sssp": "SSS+", "sss": "SSS", "ssp": "SS+", "ss": "SS",
        "sp": "S+", "s": "S", "aaa": "AAA", "aa": "AA", "a": "A",
        "bbb": "BBB", "bb": "BB", "b": "B", "c": "C", "d": "D",
    }
    return mapping.get(rate.lower(), rate.upper())


# --- QQ Hash ---

def qq_hash(qq: str) -> int:
    h = hashlib.md5(qq.encode()).hexdigest()
    return int(h[:8], 16)


# --- 时间 ---

_CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(_CN_TZ)


def format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, _CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


# --- 密码学安全的随机选择 ---

def secure_choice(items: list) -> Any:
    return items[secrets.randbelow(len(items))]


# --- 平台适配 ---

def get_platform_adapter_name(event: AstrMessageEvent) -> str:
    name = event.get_platform_name().lower()
    if "onebot" in name or "aiocqhttp" in name or "napcat" in name:
        return "onebot"
    if "kook" in name:
        return "kook"
    return "qq_official"


def is_group_message(event: AstrMessageEvent) -> bool:
    try:
        return bool(event.get_group_id())
    except Exception:
        return False


# --- @提及解析 ---

_AT_PATTERN = re.compile(r"@(\S+)")


def extract_at_targets(event: AstrMessageEvent) -> list[str]:
    """从消息中提取 @提及 的用户 ID 列表。"""
    targets = []
    try:
        from astrbot.api.message_components import At
        for comp in event.get_messages():
            if isinstance(comp, At):
                targets.append(str(comp.qq))
    except Exception:
        pass
    if not targets:
        for m in _AT_PATTERN.finditer(event.get_message_str()):
            targets.append(m.group(1))
    return targets
