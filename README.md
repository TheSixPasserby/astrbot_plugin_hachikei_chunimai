# maimai DX & CHUNITHM 综合助手

AstrBot 插件，支持双游戏查分、搜歌、猜歌、牌桌、别名管理。

## 功能

- **查分**: B50/B30 分表、单曲成绩、全球统计、分数线计算、排行榜
- **搜索**: 按曲名/定数/BPM/曲师/谱师/别名/ID 搜索
- **猜歌**: 文字猜歌、猜曲绘
- **牌桌**: 定数表、推分建议、版牌进度、等级进度
- **别名**: 提交/投票/查询/本地别名、WebSocket 实时推送
- **双查分器**: DivingFish（水鱼）+ Lxns（落雪），按游戏分别切换
- **其他**: 每日运势、随机选歌

## 安装

1. 将本项目放入 AstrBot 的 `data/plugins/` 目录
2. 安装依赖：`pip install -r requirements.txt`
3. 重启 AstrBot

## 配置

在 AstrBot 插件管理页面中配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `bot_name` | `mai-bot` | 机器人显示名称 |
| `enable_reply` | `true` | 回复时引用用户消息 |
| `mai_divingfish_token` | — | DivingFish Developer Token |
| `http_proxy` | — | HTTP 代理地址 |
| `enable_guess_game` | `true` | 启用猜歌功能 |
| `enable_alias_push` | `false` | 启用别名 WebSocket 推送 |
| `alias_push_uuid` | — | Yuzuchan 推送 UUID |
| `request_timeout_seconds` | `30` | HTTP 超时（秒） |
| `mai_alias_source` | `yuzuchan` | 舞萌别名数据源（`yuzuchan` / `lxns`） |
| `chu_alias_source` | `lxns` | 中二别名数据源 |
| `lxns_dev_key` | — | 落雪开发者 API 密钥 |
| `lxns_user_token` | — | 落雪个人 API 密钥 |

## 快速开始

1. **绑定 QQ**：发送 `bindqq <你的QQ号>`
2. **查分**：发送 `b50` 或 `maib50`
3. **搜歌**：发送 `查歌 <关键词>`
4. **帮助**：发送 `help` 查看完整命令列表

## 命令列表

### 基础设置

| 命令 | 说明 |
|------|------|
| `bindqq <QQ>` | 绑定 QQ 号（查分必需） |
| `game maimai/chunithm` | 切换个人游戏模式 |
| `game reset` | 清除个人设置，跟随群规则 |
| `game status` | 查看当前游戏模式 |
| `更改查分器 水鱼/落雪` | 切换舞萌查分器 |

### maimai DX 查分

| 命令 | 别名 |
|------|------|
| `maib50` | `b50` |
| `maiminfo <歌曲>` | `minfo` |
| `maiginfo <歌曲> [难度]` | `ginfo` |
| `mailine <目标%> <歌曲>` | `分数线` |
| `ranking` | `查看排名` |
| `myranking` | `我的排名` |

### CHUNITHM 查分

| 命令 | 别名 |
|------|------|
| `b30` / `chub30` | — |
| `chuminfo <歌曲>` | — |

### 搜索

| 命令 | 别名 |
|------|------|
| `maisearch <关键词>` | `查歌` |
| `maibase <范围>` | `定数查歌` |
| `maibpm <BPM>` | `bpm查歌` |
| `maiartist <艺术家>` | `曲师查歌` |
| `maicharter <谱师>` | `谱师查歌` |
| `maiid <编号>` | `id` |
| `chusearch <关键词>` | — |
| `chuid <编号>` | — |

### 猜歌

| 命令 | 别名 |
|------|------|
| `maiguess` | `猜歌` |
| `maiguesspic` | `猜曲绘` |
| `maiguessreset` | `重置猜歌` |

### 牌桌与进度

| 命令 | 别名 |
|------|------|
| `maitable` | `<等级>定数表` |
| `mairise` | `推分` |

### 别名管理

| 命令 | 别名 |
|------|------|
| `aliasadd <歌曲> <别名>` | `添加别名` |
| `aliasvote <ID>` | `同意别名` |
| `aliasstatus` | `当前投票` |
| `aliaslocal <歌曲> <别名>` | `添加本地别名` |

### 管理员

| 命令 | 说明 |
|------|------|
| `maiupdate` | 刷新 maimai 曲库 |
| `aliasupdate` | 刷新别名库 |
| `maitoggle` | 群功能开关 |
| `更改别名源 <游戏> <数据源>` | 切换别名数据源 |

### 趣味功能

| 命令 | 别名 |
|------|------|
| `今日mai` | `今日运势` |
| `mai什么` | — |
| `来/随/给个 <难度><等级>` | — |

## 查分器说明

- **DivingFish（水鱼）**：`diving-fish.com`，maimai DX 查分器，需要 Developer Token
- **Lxns（落雪）**：`maimai.lxns.net`，支持 maimai DX 和 CHUNITHM，支持开发者密钥和个人令牌

默认：maimai DX → DivingFish，CHUNITHM → Lxns。可通过 `更改查分器 水鱼/落雪` 切换。

## 项目结构

```
├── main.py              # 插件入口、命令路由
├── api_client.py        # DivingFish + Yuzuchan API
├── lxns_client.py       # Lxns API 客户端
├── mai_data.py          # maimai 歌曲/别名/猜歌数据
├── chu_data.py          # CHUNITHM 歌曲数据
├── storage.py           # 用户数据、群配置持久化
├── models.py            # Pydantic 数据模型
├── errors.py            # 自定义异常
├── utils.py             # 通用工具函数
├── image_utils.py       # PIL 图片工具
├── command/
│   ├── mai_score.py     # maimai 查分（DivingFish + Lxns）
│   ├── chunithm.py      # CHUNITHM 命令
│   ├── mai_search.py    # 搜索命令
│   ├── mai_table.py     # 牌桌/进度命令
│   ├── mai_guess.py     # 猜歌游戏
│   ├── alias.py         # 别名管理 + 推送
│   └── help.py          # 帮助菜单
├── _conf_schema.json    # 配置 schema
├── metadata.yaml        # 插件元数据
└── requirements.txt     # Python 依赖
```

## 字体

图片渲染需要以下字体文件（放在 `static/fonts/` 目录）：

- `MSYH.TTC` — 微软雅黑
- `MSYHBD.TTC` — 微软雅黑粗体
- `SEGUISYM.TTF` — Segoe UI Symbol

## 许可

MIT License
