"""通用工具函数。"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# --- 密钥脱敏 ---

def mask_secret(value: str, prefix_len: int = 6, suffix_len: int = 4) -> str:
    if not value or len(value) <= prefix_len + suffix_len:
        return "***"
    return f"{value[:prefix_len]}***{value[-suffix_len:]}"


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
    import secrets
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


def get_sender_display_name(event: AstrMessageEvent) -> str:
    try:
        return event.get_sender_name() or event.get_sender_id()
    except Exception:
        return event.get_sender_id()


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


# --- 安全整数转换 ---

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
