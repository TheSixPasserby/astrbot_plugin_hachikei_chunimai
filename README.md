# astrbot_plugin_hachikei_chunimai

maimai DX & CHUNITHM 综合 AstrBot 插件：查分、搜歌、猜歌、牌桌、别名、二维码同步。

## 功能

| 状态 | 功能 |
|------|------|
| ✅ | maimai DX 查分（DivingFish / Lxns） |
| ✅ | CHUNITHM 查分（Lxns） |
| ✅ | B50 / B30 图片渲染（失败自动回退 Markdown） |
| ✅ | 帮助菜单图片渲染（含文字回退） |
| ✅ | 搜歌（曲名 / 定数 / BPM / 曲师 / 谱师 / 别名 / ID） |
| ✅ | 别名查询、投票、管理 |
| ✅ | 猜歌游戏（文字 + 曲绘） |
| ✅ | 定数表、推分建议、版牌进度 |
| ✅ | 每日运势、随机选歌 |
| ✅ | SGWCMAID 二维码同步到水鱼 / 落雪（maimai-py） |
| ✅ | 落雪 OAuth 授权绑定（refresh_token 自动续期） |
| ✅ | 水鱼 Import-Token 绑定（无需 QQ 即可查分） |
| 🚧 | CHUNITHM 牌桌 / 进度（未实现） |
| 🚧 | CHUNITHM 别名投票（未实现） |

## 安装

1. 将本项目放入 AstrBot 的 `data/plugins/` 目录
2. 在 AstrBot 面板安装依赖，或手动：

   ```
   pip install -r requirements.txt
   ```

3. 重启 AstrBot

### 依赖说明

- `maimai-py==1.6.0` — 二维码同步功能需要，含 `maimai-ffi==0.7.1`（二进制 wheel）
- Python >= 3.9
- 若 `maimai-py` 安装失败（lxml 版本冲突等），二维码同步功能不可用，其他功能正常

## 配置

在 AstrBot 插件管理页面配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `mai_divingfish_token` | — | DivingFish Developer Token |
| `divingfish_client_id` | — | DivingFish OAuth Client ID（maimai-py 1.6.0 起） |
| `divingfish_client_secret` | — | DivingFish OAuth Client Secret |
| `http_proxy` | — | HTTP 代理（所有外部 HTTP 请求统一走此代理） |
| `use_yuzuchan_proxy` | `false` | 是否走柚子查分器反代（`proxy.yuzuchan.site`） |
| `lxns_dev_key` | — | 落雪开发者 API 密钥 |
| `lxns_client_id` | — | 落雪 OAuth 应用 ID |
| `lxns_client_secret` | — | 落雪 OAuth 应用密钥 |
| `mai_alias_source` | `yuzuchan` | 舞萌别名源 |
| `chu_alias_source` | `lxns` | 中二别名源 |

## 用户命令

| 命令 | 说明 |
|------|------|
| `绑定账号` | 查看绑定状态与引导 |
| `绑定QQ <QQ号>` / `解绑QQ` | 绑定 / 解绑 QQ |
| `绑定落雪` / `解绑落雪` | 落雪 OAuth 授权 / 解绑 |
| `绑定水鱼` / `解绑水鱼` | 水鱼 Import-Token 绑定（5 分钟监听）/ 解绑 |
| `更改游戏 舞萌/中二` | 切换查询游戏 |
| `更改查分器 水鱼/落雪` | 切换 maimai 查分器 |
| `同步数据 水鱼/落雪` | 街机二维码同步成绩 |
| `b50` / `chub30` | Best 50 / Best 30 分表 |
| `minfo` / `chuminfo` | 单曲成绩 |
| `查歌 <关键词>` | 搜索歌曲 |
| `猜歌` / `猜曲绘` | 猜歌游戏 |
| `帮助` | 查看完整命令 |
| `管理帮助` | 管理员命令菜单 |

未绑定时发送 `b50` / `minfo` 会给出绑定指引，而不是干巴巴的「用户不存在」。

## 测试

纯函数 + 插件加载冒烟测试，共 128 个用例：

```
pytest tests
```

## 项目结构

```
├── main.py              # 入口：命令注册、生命周期、薄委托路由
├── api_client.py        # DivingFish + Yuzuchan API
├── lxns_client.py       # Lxns API
├── qr_sync.py           # 二维码同步（maimai-py）
├── mai_data.py          # maimai 歌曲/别名数据
├── chu_data.py          # CHUNITHM 歌曲数据
├── storage.py           # 用户/群配置持久化
├── models.py            # Pydantic 模型
├── unified.py           # 统一成绩模型（DivingFish / Lxns / CHUNITHM）
├── errors.py            # 异常定义与中文文案
├── utils.py             # 工具函数
├── cover.py             # 封面缓存
├── image_utils.py       # PIL 工具
├── command/
│   ├── account.py       # 账号绑定（QQ / 落雪 / 水鱼）
│   ├── admin.py         # 管理命令（切游戏 / 查分器 / 别名源 / 数据更新）
│   ├── sync.py          # 同步数据（SGWCMAID 二维码）
│   ├── nlp.py           # 自然语言路由（猜歌 / 运势 / 别名查歌等）
│   ├── mai_score.py     # maimai 查分（DivingFish + Lxns）
│   ├── chu_score.py     # CHUNITHM 命令
│   ├── mai_search.py    # 搜索
│   ├── mai_table.py     # 牌桌 / 进度 / 推分
│   ├── mai_guess.py     # 猜歌
│   ├── alias.py         # 别名管理
│   ├── fun.py           # 运势 / 随机选歌
│   └── help.py          # 帮助菜单
├── render/
│   ├── b50.py           # maimai B50 图片渲染
│   ├── b30.py           # CHUNITHM B30 图片渲染
│   ├── help.py          # 帮助图渲染
│   ├── font.py          # 字体加载
│   ├── emoji.py         # emoji → 单色符号回退
│   └── cache.py         # 渲染缓存
├── tests/               # 单元测试 + 插件加载冒烟测试
├── tools/               # 本地预览脚本（preview_b50 / b30 / render）
├── _conf_schema.json    # 配置 schema
├── metadata.yaml        # 插件元数据
└── requirements.txt     # 依赖
```

## 许可

MIT License
