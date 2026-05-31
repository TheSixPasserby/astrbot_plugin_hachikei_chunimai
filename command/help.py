"""帮助菜单 — Markdown 输出，不依赖 Chromium。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

HELP_TEXT = """\
# 🎵 音游综合助手

## 🔗 绑定
- `bindqq <QQ号>` — 绑定 QQ 号（用于查分）
- `game maimai/chunithm` — 切换个人游戏
- `game reset` — 清除个人设置，跟随群规则
- `game group maimai/chunithm` — (管理员) 设置群默认
- `game status` — 查看当前游戏模式
- `切换(舞萌/中二)查分器 (水鱼/落雪)` — 切换查分器

> ⚠️ **首次使用请先执行 `bindqq <你的QQ号>` 绑定 QQ**，否则查分命令无法找到你。
> 个人设置优先于群默认，未设置则默认 maimai。

## 📊 查分 ⭐
- `maib50` / `b50` — Best 50 图片
- `maiminfo <歌曲>` / `minfo` — 个人成绩
- `maiginfo <歌曲> <难度>` / `ginfo` — 全球统计
- `mailine <目标%> <歌曲>` / `分数线` — 容错计算
- `<定数>的<达成率>是多少分` — 分数计算

## 🔍 搜索 ⭐
- `maisearch <关键词>` / `查歌` — 搜索歌曲
- `maibase <范围>` / `定数查歌` — 按定数
- `maibpm <BPM>` / `bpm查歌` — 按 BPM
- `maiartist <艺术家>` / `曲师查歌` — 按曲师
- `maicharter <谱师>` / `谱师查歌` — 按谱师
- `maiid <编号>` / `id` — 按 ID
- `<别名>是什么歌` — 别名查询

## 🎮 猜歌 ⭐
- `maiguess` / `猜歌` — 开始猜歌
- `maiguesspic` / `猜曲绘` — 猜曲绘
- `maiguessreset` / `重置猜歌` — 强制结束
- `maiguesstoggle` — 管理员开关

## 📋 牌桌与进度 ⭐
- `maitable` / `<等级>定数表` — 定数表
- `mairise` / `推分` — 推分建议
- `<版本><等级>进度` — 版牌进度
- `<等级> <评价> 进度` — 等级进度

## 📊 排名（共用）
- `ranking` / `查看排名` — 排行榜
- `myranking` / `我的排名` — 我的排名

## 🏷️ 别名（共用）
- `aliasadd` / `添加别名` — 提交别名
- `aliasvote` / `同意别名` — 投票
- `aliasstatus` / `当前投票` — 查看投票
- `<歌曲>有什么别名` — 查询别名
- `aliastoggle` — 群推送开关
- `aliaslocal` / `添加本地别名` — 本地别名

## 🕹️ 机厅排队（共用）
- `arcadeadd/del/edit` — 管理机厅
- `arcadesub` / `订阅机厅` — 群订阅
- `<机厅>加/减/设 Y人` — 更新人数
- `机厅几人` / `jtj` — 查看所有
- `<机厅>有几人` / `jr` — 查看单个

## 🔧 管理
- `maiupdate` — 刷新曲库
- `aliasupdate` — 刷新别名
- `maitoggle` — 群功能开关

## 🎲 其他
- `今日mai` / `今日运势` — 每日运势
- `mai什么` — 随机推荐
- `来/随/给个 <难度><等级>` — 随机选歌
"""


async def help_handler(event: AstrMessageEvent):
    yield event.make_result().use_markdown(True).message(HELP_TEXT)
