# Changelog

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
