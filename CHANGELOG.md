# Changelog

## v0.2.7 (2026-10-03)

### 重构
- 从 `main.py` 拆出账号绑定到 `command/account.py`（`AccountService`）
- 绑定相关 pending 状态（OAuth 密钥 / 水鱼 Token）从 main 迁移到 service
- 命令方法变为薄委托，`main.py` 1436 → 1171 行

## v0.2.6 (2026-10-03)

### 重构
- 从 `main.py` 拆出趣味功能到 `command/fun.py`（今日运势 / mai什么 / 随机选歌）
- 清理 `main.py` 未使用的导入（`get_platform_adapter_name`、`MaimaiError`、`describe_error`）

## v0.2.5 (2026-10-03)

### 新增
- CHUNITHM B30 图片渲染 `render/b30.py`（Best 30 / Selection 10 / New Best 20）
- `cover.py` 支持 CHUNITHM 封面源（Lxns jacket，`static/cover_chu`）
- B30 图片优先发送，渲染失败自动回退 Markdown
- 本地预览工具 `tools/preview_b30.py`

## v0.2.4 (2026-10-03)

### 新增
- 统一成绩模型 `unified.py`（DivingFish / Lxns maimai / CHUNITHM → `UnifiedScore`）
- 封面永久缓存 `cover.py`（并发限制、DX/SD ID fallback、失败占位图、代理支持）
- maimai B50 图片渲染 `render/b50.py`（水鱼 / 落雪两个查分器共用）
- B50 图片优先发送，渲染失败自动回退 Markdown 文本
- 本地预览工具 `tools/preview_b50.py`

## v0.2.3 (2026-10-03)

### 修复
- 帮助图 emoji 全部显示为方框（Pillow 用 CJK 字体渲染彩色 emoji 无字形）

### 新增
- `render/emoji.py`：emoji → 单色符号回退（渲染图片前统一转换）

## v0.2.2 (2026-06-06)

### 修复
- 水鱼 Token 绑定失效（@mention 混入文本导致验证失败）
- bot 自身消息触发 token 监听
- `_df_bind_and_switch` async generator 不能 await
- QQ 提取崩溃（`qq_official` 不是数字）
- 推分建议用错查分器（现在按 `更改查分器` 设置走）
- 定数表改用 Markdown 格式 + 难度列

### 清理
- 删除 `image_utils.py` 中 6 个未使用函数
- 删除 `api_client.py` 中 `MaiCover`、`qqlogo`
- 核心路由加日志（B50/minfo/sync/oauth）

## v0.2.1 (2026-06-02)

### 修复
- async generator 不能 await（_try_df_token）
- QQ 提取崩溃（table handler 中 int(at_targets[0])）
- 推分建议支持 Lxns API
- 定数表 Markdown 格式

## v0.2.0 (2026-06-02)

### 重构
- `chunithm.py` → `chu_score.py`，命名统一
- 文件重命名：`music_data.py` → `mai_data.py`、`chunithm_data.py` → `chu_data.py`
- 所有 maimai handler 加 `mai_` 前缀（`b50_handler` → `mai_b50_handler` 等）
- 配置键重命名：`maimaidxtoken` → `mai_divingfish_token`、`maimai_http_proxy` → `http_proxy`
- 命令中文化：`绑定QQ`、`更改游戏 舞萌/中二`、`绑定落雪`、`绑定水鱼`、`同步数据`
- `MaimaiPlugin` → `MaiChuPlugin`

### 新增
- SGWCMAID 二维码同步（maimai-py）
- 落雪 OAuth 授权绑定（refresh_token 自动续期）
- 水鱼 Import-Token 绑定（5 分钟监听模式）
- `绑定账号` 命令查看绑定状态
- `解绑落雪` / `解绑水鱼` 命令
- `同步数据 水鱼/落雪` 命令
- `ahelp` / `管理帮助` 管理员命令菜单
- 插件重载时自动验证落雪 token 有效性
- CHUNITHM 别名查询
- 别名数据源可配置（舞萌/中二分别设置）
- 帮助菜单动态页眉（显示当前查询游戏）

### 修复
- CHUNITHM Rating 公式修正（CHUNITHM NEW+ 标准）
- CHUNITHM 评级阈值修正（SSS+ 1009000）
- `chu_rating` 截断到小数点后两位（街机行为）
- Lxns API 公共接口去除错误的认证头
- `find_by_id` 非数字输入不再崩溃
- guess solve handler `return` 位置修复
- `CHU_CLEAR_LABELS` 导入缺失修复

### 代码清理
- 删除机厅功能（arcade_data.py、command/arcade.py）
- 删除未使用的模型（TableData、PlanInfo、RiseScore）
- 删除未使用的函数（format_ts、require_qq）
- 删除未使用的导入（UserInfo、achievements_label、MaimaiError）
- 修复 storage.py 中重复的 `import time`
- 修复 main.py 中重复的 `import re`
- 删除空的 chunithm TODO 死代码
- 删除 sync.bat、static/config.json、tests/
- 更新 README（标注半成品状态）

## v0.1.0 (2026-05-31)

- 初始版本
