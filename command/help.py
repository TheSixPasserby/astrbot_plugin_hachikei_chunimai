"""帮助菜单 — Markdown 输出，不依赖 Chromium。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


# 结构化帮助数据：文本帮助与图片帮助共用一份数据。
# 结构：分类 -> {emoji, commands: [{cmd, alias, desc, star(是否支持游戏路由), admin}]}
HELP_SECTIONS: dict[str, dict] = {
    "maimai_score": {
        "emoji": "📊",
        "title": "maimai DX 查分",
        "commands": [
            {"cmd": "maib50", "alias": "b50", "desc": "Best 50 分表", "star": True},
            {"cmd": "maiminfo <歌曲>", "alias": "minfo", "desc": "个人成绩查询", "star": True},
            {"cmd": "maiginfo <歌曲> <难度>", "alias": "ginfo", "desc": "全球统计", "star": True},
            {"cmd": "mailine <目标%> <歌曲>", "alias": "分数线", "desc": "容错分数线计算", "star": True},
            {"cmd": "<定数>的<达成率>是多少分", "alias": "—", "desc": "分数计算", "star": False},
            {"cmd": "ranking", "alias": "查看排名", "desc": "查分器排行榜", "star": False},
            {"cmd": "myranking", "alias": "我的排名", "desc": "我的排名", "star": False},
        ],
    },
    "chu_score": {
        "emoji": "📊",
        "title": "CHUNITHM 查分",
        "commands": [
            {"cmd": "chub30", "alias": "b30", "desc": "Best 30 分表", "star": False},
            {"cmd": "chuminfo <歌曲>", "alias": "—", "desc": "个人成绩查询", "star": False},
        ],
    },
    "search": {
        "emoji": "🔍",
        "title": "搜索歌曲",
        "commands": [
            {"cmd": "maisearch <关键词>", "alias": "查歌", "desc": "按曲名搜索", "star": True},
            {"cmd": "maibase <范围>", "alias": "定数查歌", "desc": "按定数搜索", "star": True},
            {"cmd": "maibpm <BPM>", "alias": "bpm查歌", "desc": "按 BPM 搜索", "star": True},
            {"cmd": "maiartist <艺术家>", "alias": "曲师查歌", "desc": "按曲师搜索", "star": True},
            {"cmd": "maicharter <谱师>", "alias": "谱师查歌", "desc": "按谱师搜索", "star": True},
            {"cmd": "maiid <编号>", "alias": "id", "desc": "按 ID 查询", "star": True},
            {"cmd": "chusearch <关键词>", "alias": "—", "desc": "CHUNITHM 搜歌", "star": False},
            {"cmd": "chuid <编号>", "alias": "—", "desc": "CHUNITHM ID 查询", "star": False},
            {"cmd": "<别名>是什么歌", "alias": "—", "desc": "别名查询", "star": False},
        ],
    },
    "guess": {
        "emoji": "🎮",
        "title": "猜歌游戏",
        "commands": [
            {"cmd": "maiguess", "alias": "猜歌", "desc": "文字猜歌", "star": False},
            {"cmd": "maiguesspic", "alias": "猜曲绘", "desc": "看封面猜歌", "star": False},
            {"cmd": "maiguessreset", "alias": "重置猜歌", "desc": "强制结束当前猜歌", "star": False},
        ],
    },
    "table": {
        "emoji": "📋",
        "title": "牌桌与进度",
        "commands": [
            {"cmd": "maitable", "alias": "<等级>定数表", "desc": "定数表", "star": False},
            {"cmd": "mairise", "alias": "推分", "desc": "推分建议", "star": False},
            {"cmd": "<版本><等级>进度", "alias": "—", "desc": "版牌完成进度", "star": False},
            {"cmd": "<等级> <评价> 进度", "alias": "—", "desc": "等级评价进度", "star": False},
        ],
    },
    "alias": {
        "emoji": "🏷️",
        "title": "别名管理",
        "commands": [
            {"cmd": "aliasadd <歌曲> <别名>", "alias": "添加别名", "desc": "提交新别名", "star": False},
            {"cmd": "aliasvote <ID>", "alias": "同意别名", "desc": "投票支持", "star": False},
            {"cmd": "aliasstatus", "alias": "当前投票", "desc": "查看待投票", "star": False},
            {"cmd": "<歌曲>有什么别名", "alias": "—", "desc": "查询歌曲别名", "star": False},
            {"cmd": "aliaslocal <歌曲> <别名>", "alias": "添加本地别名", "desc": "仅本群可用", "star": False},
        ],
    },
    "fun": {
        "emoji": "🎲",
        "title": "趣味功能",
        "commands": [
            {"cmd": "今日mai", "alias": "今日运势", "desc": "每日运势", "star": False},
            {"cmd": "mai什么", "alias": "—", "desc": "随机推荐歌曲", "star": False},
            {"cmd": "来/随/给个 <难度><等级>", "alias": "—", "desc": "随机选歌", "star": False},
        ],
    },
}


def build_help_text(current_game: str = "maimai", group_game: str | None = None) -> str:
    """构建帮助文本，带动态页眉。"""
    game_label = "maimai DX" if current_game == "maimai" else "CHUNITHM"

    header = f"# 🎵 maimai DX & CHUNITHM 综合助手\n\n🎮 当前查询游戏: **{game_label}**"
    if group_game is not None:
        group_label = "maimai DX" if group_game == "maimai" else "CHUNITHM"
        header += f"  |  群默认: **{group_label}**"

    return f"""\
{header}

> 首次使用请发送 **`绑定账号`** 查看绑定指引。
> 带 ⭐ 的命令支持查询游戏路由：前缀 `mai`/`chu` 可强制指定游戏。
> 发送「同步数据 水鱼/落雪」后发送街机二维码即可同步成绩。

---

## 📊 maimai DX 查分

| 命令 | 别名 | 说明 |
|------|------|------|
| `maib50` | `b50` ⭐ | Best 50 分表 |
| `maiminfo <歌曲>` | `minfo` ⭐ | 个人成绩查询 |
| `maiginfo <歌曲> <难度>` | `ginfo` ⭐ | 全球统计 |
| `mailine <目标%> <歌曲>` | `分数线` ⭐ | 容错分数线计算 |
| `<定数>的<达成率>是多少分` | — | 分数计算 |
| `ranking` | `查看排名` | 查分器排行榜 |
| `myranking` | `我的排名` | 我的排名 |

## 📊 CHUNITHM 查分

| 命令 | 别名 | 说明 |
|------|------|------|
| `chub30` | `b30` | Best 30 分表 |
| `chuminfo <歌曲>` | — | 个人成绩查询 |

---

## 🔍 搜索歌曲

| 命令 | 别名 | 说明 |
|------|------|------|
| `maisearch <关键词>` | `查歌` ⭐ | 按曲名搜索 |
| `maibase <范围>` | `定数查歌` ⭐ | 按定数搜索 |
| `maibpm <BPM>` | `bpm查歌` ⭐ | 按 BPM 搜索 |
| `maiartist <艺术家>` | `曲师查歌` ⭐ | 按曲师搜索 |
| `maicharter <谱师>` | `谱师查歌` ⭐ | 按谱师搜索 |
| `maiid <编号>` | `id` ⭐ | 按 ID 查询 |
| `chusearch <关键词>` | — | CHUNITHM 搜歌 |
| `chuid <编号>` | — | CHUNITHM ID 查询 |
| `<别名>是什么歌` | — | 别名查询 |

---

## 🎮 猜歌游戏

| 命令 | 别名 | 说明 |
|------|------|------|
| `maiguess` | `猜歌` | 文字猜歌 |
| `maiguesspic` | `猜曲绘` | 看封面猜歌 |
| `maiguessreset` | `重置猜歌` | 强制结束当前猜歌 |

---

## 📋 牌桌与进度

| 命令 | 别名 | 说明 |
|------|------|------|
| `maitable` | `<等级>定数表` | 定数表 |
| `mairise` | `推分` | 推分建议 |
| `<版本><等级>进度` | — | 版牌完成进度 |
| `<等级> <评价> 进度` | — | 等级评价进度 |

---

## 🏷️ 别名管理

| 命令 | 别名 | 说明 |
|------|------|------|
| `aliasadd <歌曲> <别名>` | `添加别名` | 提交新别名 |
| `aliasvote <ID>` | `同意别名` | 投票支持 |
| `aliasstatus` | `当前投票` | 查看待投票 |
| `<歌曲>有什么别名` | — | 查询歌曲别名 |
| `aliaslocal <歌曲> <别名>` | `添加本地别名` | 仅本群可用 |

---

## 🎲 趣味功能

| 命令 | 别名 | 说明 |
|------|------|------|
| `今日mai` | `今日运势` | 每日运势 |
| `mai什么` | — | 随机推荐歌曲 |
| `来/随/给个 <难度><等级>` | — | 随机选歌 |
"""


ADMIN_HELP_TEXT = """\
# 🔧 管理员命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `更改游戏 群 舞萌/中二` | — | 设置群默认查询游戏 |
| `更改查分器 水鱼/落雪` | `切换查分器` | 切换舞萌查分器 |
| `更改别名源 <游戏> <数据源>` | `切换别名源` | 切换别名数据源 |
| `gametoggle` | `开启/关闭功能` | 群功能开关 |
| `maiguesstoggle` | `开启/关闭猜歌` | 群猜歌开关 |
| `aliastoggle` | `开启/关闭别名推送` | 群别名推送开关 |
| `maiupdate` | `更新maimai数据` | 刷新 maimai 曲库 |
| `aliasupdate` | `更新别名库` | 刷新别名库 |
"""


def _render_help_image_sync(current_game: str, group_game: str | None) -> str | None:
    """渲染帮助图为 base64（同步，CPU-bound）。失败返回 None。"""
    try:
        from ..render.help import render_help
        from ..image_utils import image_to_base64

        img = render_help(HELP_SECTIONS, current_game=current_game, group_game=group_game)
        return image_to_base64(img)
    except Exception:
        return None


async def help_handler(
    event: AstrMessageEvent,
    current_game: str = "maimai",
    group_game: str | None = None,
):
    # 优先图片帮助，失败回退 Markdown 文本；渲染放到线程池避免阻塞事件循环
    import asyncio

    try:
        b64 = await asyncio.to_thread(_render_help_image_sync, current_game, group_game)
    except Exception:
        b64 = None
    if b64:
        yield event.make_result().base64_image(b64)
        return
    yield event.make_result().use_markdown(True).message(
        build_help_text(current_game, group_game)
    )


async def admin_help_handler(event: AstrMessageEvent):
    yield event.make_result().use_markdown(True).message(ADMIN_HELP_TEXT)
