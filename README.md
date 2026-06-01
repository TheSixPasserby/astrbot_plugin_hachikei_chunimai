# astrbot_plugin_hachikei_chunimai

> ⚠️ **半成品项目，AI coding 堆出来的屎山。** 能用，但别指望代码质量。
> 功能会逐步完善，欢迎提 issue，但请不要 review 代码然后感到绝望。

maimai DX & CHUNITHM 综合 AstrBot 插件。

## 功能

| 状态 | 功能 |
|------|------|
| ✅ | maimai DX 查分（DivingFish / Lxns） |
| ✅ | CHUNITHM 查分（Lxns） |
| ✅ | 搜歌（曲名/定数/BPM/曲师/谱师/别名/ID） |
| ✅ | 别名查询、投票、管理 |
| ✅ | 猜歌游戏 |
| ✅ | 定数表、推分建议、版牌进度 |
| ✅ | 每日运势、随机选歌 |
| ✅ | SGWCMAID 二维码同步（maimai-py） |
| ✅ | 落雪 OAuth 授权绑定 |
| 🚧 | CHUNITHM 牌桌/进度（未实现） |
| 🚧 | CHUNITHM 别名投票（未实现） |
| ❌ | 图片版分表（纯文本 Markdown） |

## 安装

1. 将本项目放入 AstrBot 的 `data/plugins/` 目录
2. 在 AstrBot 面板安装依赖，或手动：
   ```
   pip install -r requirements.txt
   ```
3. 重启 AstrBot

### 依赖说明

- `maimai-py==1.4.3` — 二维码同步功能需要，含 `maimai-ffi==0.7.0`（二进制 wheel）
- Python >= 3.9
- Windows x64 + Python 3.10 已验证

如果 `maimai-py` 安装失败（lxml 版本冲突等），二维码同步功能不可用，其他功能正常。

## 配置

在 AstrBot 插件管理页面配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `mai_divingfish_token` | — | DivingFish Developer Token |
| `http_proxy` | — | HTTP 代理 |
| `lxns_dev_key` | — | 落雪开发者 API 密钥 |
| `lxns_client_id` | — | 落雪 OAuth 应用 ID |
| `lxns_client_secret` | — | 落雪 OAuth 应用密钥 |
| `mai_alias_source` | `yuzuchan` | 舞萌别名源 |
| `chu_alias_source` | `lxns` | 中二别名源 |

## 用户命令

| 命令 | 说明 |
|------|------|
| `绑定账号` | 查看绑定状态与引导 |
| `绑定QQ <QQ号>` | 绑定 QQ |
| `绑定落雪` | 落雪 OAuth 授权 |
| `绑定水鱼 <Token>` | 绑定水鱼 Import-Token |
| `更改游戏 舞萌/中二` | 切换查询游戏 |
| `同步数据 水鱼/落雪` | 街机二维码同步成绩 |
| `b50` / `chub30` | Best 分表 |
| `minfo` / `chuminfo` | 单曲成绩 |
| `查歌 <关键词>` | 搜索歌曲 |
| `猜歌` / `猜曲绘` | 猜歌游戏 |
| `帮助` | 查看完整命令 |

## 已知问题

- 代码是 AI 逐步生成的，命名、结构、错误处理不一致
- 部分功能只实现了 maimai DX，CHUNITHM 对应功能缺失
- 图片渲染基本没用，全靠 Markdown 文本
- `image_utils.py` 大量代码闲置
- 没有测试
- 很多 try/except 静默吞异常

## 项目结构

```
├── main.py              # 入口，命令路由（~1100 行，该拆）
├── qr_sync.py           # 二维码同步（maimai-py）
├── api_client.py        # DivingFish + Yuzuchan API
├── lxns_client.py       # Lxns API
├── mai_data.py          # maimai 歌曲/别名数据
├── chu_data.py          # CHUNITHM 歌曲数据
├── storage.py           # 用户/群配置持久化
├── models.py            # Pydantic 模型
├── errors.py            # 异常定义
├── utils.py             # 工具函数
├── image_utils.py       # PIL 工具（基本没用）
├── command/
│   ├── mai_score.py     # maimai 查分（DivingFish + Lxns）
│   ├── chunithm.py      # CHUNITHM 命令
│   ├── mai_search.py    # 搜索
│   ├── mai_table.py     # 牌桌/进度
│   ├── mai_guess.py     # 猜歌
│   ├── alias.py         # 别名管理
│   └── help.py          # 帮助菜单
├── _conf_schema.json    # 配置 schema
├── metadata.yaml        # 插件元数据
└── requirements.txt     # 依赖
```

## 许可

MIT License
