# maimai DX 综合助手

AstrBot 插件，提供 maimai DX 全功能支持。

## 功能

- **查分**: B50、minfo、ginfo、分数线、分数计算、排行榜
- **搜索**: 标题/定数/BPM/曲师/谱师/别名/ID 搜索
- **猜歌**: 猜歌、猜曲绘游戏
- **牌桌**: 定数表、完成表、版牌进度、等级进度、推分建议
- **别名**: 别名查询、添加、投票、WebSocket 推送
- **机厅**: 机厅管理、订阅、排队人数跟踪
- **其他**: 每日运势、随机选歌

## 安装

1. 将本目录放入 AstrBot 的 `plugins` 目录
2. 安装依赖: `pip install -r requirements.txt`
3. 在 AstrBot 管理面板中配置 DivingFish Token（可选）

## 配置

在 AstrBot 管理面板中配置:

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `bot_name` | 机器人名称 | `mai-bot` |
| `maimaidxtoken` | DivingFish Token | 空 |
| `enable_guess_game` | 启用猜歌 | `true` |
| `enable_arcade` | 启用机厅 | `true` |
| `enable_alias_push` | 启用别名推送 | `false` |
| `request_timeout_seconds` | 请求超时 | `30` |

## 帮助

发送 `帮助maimaiDX` 查看完整命令列表（Markdown 格式）。

## 依赖

- `aiohttp` - HTTP 客户端
- `aiofiles` - 异步文件 I/O
- `Pillow` - 图片生成
- `pydantic` - 数据验证
- `numpy` - 图像处理（猜歌裁切）

## 字体

需要在 `static/fonts/` 目录下放置以下字体文件（用于图片生成）:
- `ShangguMonoSC-Regular.otf`
- `ResourceHanRoundedCN-Bold.ttf`
- `Torus SemiBold.otf`
