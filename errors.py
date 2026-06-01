"""自定义异常类。"""

from __future__ import annotations


class MaimaiError(Exception):
    """maimai 相关操作的基础异常。"""


class UserNotFoundError(MaimaiError):
    """用户在查分器中未找到。"""


class UserNotExistsError(MaimaiError):
    """用户不存在。"""


class UserDisabledQueryError(MaimaiError):
    """用户关闭了查询功能。"""


class TokenError(MaimaiError):
    """Token 相关错误。"""


class TokenNotFoundError(TokenError):
    """Token 未找到。"""


class TokenDisableError(TokenError):
    """Token 已被禁用。"""


class ServerError(MaimaiError):
    """服务器错误。"""


class MusicNotPlayError(MaimaiError):
    """歌曲未游玩。"""


class MusicNotFoundError(MaimaiError):
    """歌曲未找到。"""


class AliasNotFoundError(MaimaiError):
    """别名未找到。"""


class PermissionDeniedError(MaimaiError):
    """权限不足。"""


class MaimaiDependencyError(MaimaiError):
    """依赖库缺失或版本不兼容。"""


# 异常 -> 用户友好中文消息 的映射
_ERROR_MESSAGES: dict[type[MaimaiError], str] = {
    UserNotFoundError: "未在查分器中找到该用户，请先在 diving-fish.com 绑定账号。",
    UserNotExistsError: "用户不存在。",
    UserDisabledQueryError: "该用户关闭了查询功能。",
    TokenNotFoundError: "未找到 Token，请先使用 `maimaitoken` 绑定。",
    TokenDisableError: "Token 已被禁用，请在查分器中重新启用。",
    TokenError: "Token 错误，请重新绑定。",
    ServerError: "查分器服务器错误，请稍后再试。",
    MusicNotPlayError: "未查询到该歌曲的游玩记录。",
    MusicNotFoundError: "未找到匹配的歌曲。",
    AliasNotFoundError: "未找到匹配的别名。",
    PermissionDeniedError: "权限不足，需要管理员权限。",
}


def describe_error(exc: Exception) -> str:
    """将异常转换为用户友好的中文消息。"""
    if isinstance(exc, MaimaiDependencyError):
        return f"依赖错误：{exc}"
    for exc_type, msg in _ERROR_MESSAGES.items():
        if isinstance(exc, exc_type):
            return msg
    return f"未知错误：{type(exc).__name__}: {exc}"
