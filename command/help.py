"""帮助菜单 — Markdown 输出，不依赖 Chromium。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

HELP_TEXT = """\
# 🎵 maimai DX & CHUNITHM 综合助手

> 首次使用请先 **`bindqq <QQ号>`** 绑定 QQ，否则查分命令无法找到你。
> 带 ⭐ 的命令支持游戏模式路由：前缀 `mai`/`chu` 可强制指定游戏。

---

## ⚙️ 基础设置

| 命令 | 说明 |
|------|------|
| `bindqq <QQ>` | 绑定 QQ 号（查分必需） |
| `game maimai/chunithm` | 切换个人游戏模式 |
| `game reset` | 清除个人设置，跟随群规则 |
| `game status` | 查看当前游戏模式 |
| `game group maimai/chunithm` | *(管理员)* 设置群默认游戏 |
| `更改查分器 水鱼/落雪` | 切换舞萌查分器 |

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
| `b30` / `chub30` | — | Best 30 分表 |
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
| `maiguesstoggle` | — | *(管理员)* 开关猜歌功能 |

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
| `aliastoggle` | — | 开关别名推送 |

---

## 🔧 管理员

| 命令 | 别名 | 说明 |
|------|------|------|
| `maiupdate` | `更新maimai数据` | 刷新 maimai 曲库 |
| `aliasupdate` | `更新别名库` | 刷新别名库 |
| `maitoggle` | — | 群功能开关 |
| `更改别名源 <游戏> <数据源>` | `切换别名源` | 切换舞萌/中二的别名数据源 |

---

## 🎲 趣味功能

| 命令 | 别名 | 说明 |
|------|------|------|
| `今日mai` | `今日运势` | 每日运势 |
| `mai什么` | — | 随机推荐歌曲 |
| `来/随/给个 <难度><等级>` | — | 随机选歌 |
"""


async def help_handler(event: AstrMessageEvent):
    yield event.make_result().use_markdown(True).message(HELP_TEXT)
