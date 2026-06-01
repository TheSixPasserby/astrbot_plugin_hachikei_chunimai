"""帮助菜单 — Markdown 输出，不依赖 Chromium。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


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
> 发送「绑定 SGWCMAID...」绑定街机账号，再用「同步数据 水鱼/落雪」同步成绩。

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


async def help_handler(
    event: AstrMessageEvent,
    current_game: str = "maimai",
    group_game: str | None = None,
):
    yield event.make_result().use_markdown(True).message(
        build_help_text(current_game, group_game)
    )


async def admin_help_handler(event: AstrMessageEvent):
    yield event.make_result().use_markdown(True).message(ADMIN_HELP_TEXT)
