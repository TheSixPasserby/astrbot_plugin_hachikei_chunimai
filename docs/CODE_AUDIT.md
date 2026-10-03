# Repository Audit — astrbot_plugin_hachikei_chunimai

> 只读审计，未改任何代码。审计基点为 `main` @ `411b158`。
> 生成日期：2026-10-03

---

## 0.5.1 命令清单

### 注册点与 alias（`main.py`，48 个 `@command`）

| 命令 | alias | 游戏路由 | 权限 | 状态 |
|------|-------|---------|------|------|
| `更改游戏` | `game`、`切换游戏` | — | 群默认需管理员 | ✅ |
| `switchprober` | `切换查分器`、`更改查分器` | 仅 maimai | 无（群级） | ✅ |
| `绑定QQ` | — | — | 无 | ✅ |
| `bindlxns` | `绑定落雪` | — | 无 | ✅ |
| `unbindlxns` | `解绑落雪` | — | 无 | ✅ |
| `binddf` | `绑定水鱼` | — | 无 | ✅ |
| `unbinddf` | `解绑水鱼` | — | 无 | ✅ |
| `account` | `绑定账号`、`账号状态`、`我的绑定` | — | 无 | ✅ |
| `help` | `帮助` | ⭐ 动态页眉 | 无 | ✅ |
| `ahelp` | `管理帮助` | — | 管理员 | ✅ |
| `gametoggle` | `开启功能`、`关闭功能`、`maitoggle` | — | 管理员 | ✅ |
| `switchalias` | `更改别名源`、`切换别名源` | 舞萌/中二 | 管理员 | ✅ |
| `maiupdate` | `更新maimai数据` | — | 管理员 | ✅ |
| `maib50` | — | 强制 maimai | 无 | ✅ |
| `maiminfo` | — | 强制 maimai | 无 | ✅ |
| `maiginfo` | — | 强制 maimai | 无 | ✅ |
| `mailine` | — | 强制 maimai | 无 | ✅ |
| `chub30` | `b30` | 强制 CHUNITHM | 无 | ✅ |
| `chuminfo` | — | 强制 CHUNITHM | 无 | ✅ |
| `chusearch` | — | 强制 CHUNITHM | 无 | ✅ |
| `chuid` | — | 强制 CHUNITHM | 无 | ✅ |
| `b50` | — | ⭐ | 无 | ✅ |
| `minfo` | — | ⭐ | 无 | ✅ |
| `ginfo` | — | ⭐ | 无 | ✅ |
| `分数线` | — | ⭐ | 无 | ✅ |
| `查歌` | — | ⭐ | 无 | ✅ |
| `id` | — | ⭐ | 无 | ✅ |
| `ranking` | `查看排名`、`查看排行` | ⭐（CHUNITHM 无） | 无 | ✅ |
| `myranking` | `我的排名` | ⭐（CHUNITHM 无） | 无 | ✅ |
| `maisearch` | — | 强制 maimai | 无 | ✅ |
| `maibase` | — | 强制 maimai | 无 | ✅ |
| `maibpm` | — | 强制 maimai | 无 | ✅ |
| `maiartist` | — | 强制 maimai | 无 | ✅ |
| `maicharter` | — | 强制 maimai | 无 | ✅ |
| `maiid` | — | 强制 maimai | 无 | ✅ |
| `maiguess` | — | 强制 maimai | 无 | ✅ |
| `maiguesspic` | — | 强制 maimai | 无 | ✅ |
| `maiguessreset` | — | 强制 maimai | 无 | ✅ |
| `maiguesstoggle` | — | 强制 maimai | 管理员 | ✅ |
| `maitable` | — | 强制 maimai | 无 | ✅ |
| `mairise` | — | 强制 maimai | 无 | ✅ |
| `aliasupdate` | `更新别名库` | ⭐ | 管理员 | ✅ |
| `aliasadd` | `添加别名`、`增加别名`、`增添别名`、`添加别称` | ⭐ | 无 | ✅ |
| `aliaslocal` | `添加本地别名`、`添加本地别称` | ⭐ | 无 | ✅ |
| `aliasvote` | `同意别名`、`同意别称` | ⭐ | 无 | ✅ |
| `aliasstatus` | `当前投票`、`当前别名投票`、`当前别称投票` | ⭐ | 无 | ✅ |
| `aliastoggle` | `开启别名推送`、`关闭别名推送` | — | 无 | ✅ |
| `syncdata` | `同步数据` | — | 无 | ✅ |

### 无前缀自然语言监听（`_on_message`，`EventMessageType.ALL`）

| 触发 | 处理器 | 游戏 |
|------|--------|------|
| OAuth code 监听（`_pending_oauth`） | `_try_oauth_code` | — |
| 水鱼 Token 监听（`_pending_df`） | `_try_df_token` | — |
| `SGWCMAID...`（同步等待中） | `_try_sync_sgid` | — |
| 猜歌答案 | `mai_guess_solve_handler` | maimai 群 |
| `X的Y是多少分` | `mai_score_calc_handler` | maimai |
| `今日mai/今日舞萌/今日运势` | `_daily_fortune` | maimai |
| `.*mai.*什么` | `_mai_what` | maimai |
| `来/随/给个 <难度><等级>` | `_random_song` | maimai |
| `分数线...` | `mai_score_line_handler` | maimai |
| `X定数表` | `mai_rating_table_handler` | maimai |
| `...进度` | `mai_plate_progress_handler` | maimai |
| `我要在...` | `mai_rise_score_handler` | maimai |
| `X有什么别名` | `alias_query_handler` / `chu_alias_query_handler` | ⭐ |
| `X是什么歌/是啥歌` | `mai_search_alias_handler` / `chu_search_alias_handler` | ⭐ |

### 未实现 / 已声明但无命令注册

| 项 | 说明 |
|----|------|
| `mai_level_progress_handler` | 在 `command/mai_table.py` 定义、`main.py` 导入，但**无任何 `@command` 或无前缀路由调用**。用户无法触发「等级进度」。 |
| `mai_level_achievement_list_handler` | 同上，**无路由**。「分数列表」不可用。 |
| `alias_global_push_handler` | `main.py` 导入但**从未被调用/注册**。 |
| `filter_music()` | `mai_data.py` 定义，**全库无调用**（死代码）。 |
| `query_user_dev()` | `api_client.py` 定义，**无调用**（仅 `query_user_record_dev` 被用）。 |
| `MusicDataManager.level_data` | 在 `load_music_data` 中计算，**从未读取**。 |

---

## 0.5.2 配置清单

来源：`_conf_schema.json` 交叉检查 `main.py` / `storage.py` / `qr_sync.py`。

| key | schema 默认 | 实际读取位置 | 是否写回 | 一致性 |
|-----|------------|-------------|---------|--------|
| `bot_name` | `mai-bot` | `main.py:69` | 否 | ⚠️ 读入 `self.bot_name` 后**从未使用** |
| `enable_reply` | `true` | `main.py:70` | 否 | ⚠️ 读入 `self.enable_reply` 后**从未使用** |
| `mai_divingfish_token` | `""` | `main.py:108,138` | 否 | ✅ |
| `http_proxy` | `""` | `main.py:109,137`、`qr_sync.py` | 否 | ❌ **语义错误**（见 1.3） |
| `enable_guess_game` | `true` | **无读取** | 否 | ❌ schema 有、代码无（猜歌实际走群级 `toggle_guess`） |
| `enable_alias_push` | `false` | `main.py:131` | 否 | ✅ |
| `alias_push_uuid` | `""` | `main.py:80,131,1087` | 否 | ✅ |
| `request_timeout_seconds` | `30` | `main.py:71` | 否 | ✅ |
| `kook_token` | `""` | **无读取** | 否 | ❌ schema 有、代码无 |
| `mai_alias_source` | `yuzuchan` | `main.py:117,700` | ✅ `save_config` | ✅ |
| `chu_alias_source` | `lxns` | `main.py:700`（仅写） | ✅ | ⚠️ **从不读取**，CHUNITHM 别名固定走 `chu_data.load_aliases()`（lxns） |
| `lxns_dev_key` | `""` | `main.py:113` | 否 | ✅ |
| `lxns_client_id` | `""` | `main.py:155,362,415,614` | 否 | ✅ |
| `lxns_client_secret` | `""` | `main.py:156,363,416,615` | 否 | ✅ |

### 旧 key（历史遗留）

CHANGELOG v0.2.0 提到重命名，代码中已无残留：
- `maimaidxtoken` → `mai_divingfish_token` ✅ 已迁移
- `maimai_http_proxy` → `http_proxy` ✅ 已迁移
- `lxns_user_token` → 已删除（改 per-user OAuth，见 `git log f7fd4dc`）

---

## 0.5.3 API 清单

| API | 文件 | 用途 | 认证 | 超时 | 代理 | 错误处理 | fallback |
|-----|------|------|------|------|------|---------|----------|
| DivingFish / Yuzuchan Proxy | `api_client.py` `MaimaiAPI` | 查分/别名/排名/plate | `developer-token` header | `ClientTimeout(total=timeout)` | ❌ 见 1.3 | 状态码→`MaimaiError` 子类 | 无（上层 catch） |
| Lxns 开发者 API | `lxns_client.py` `LxnsAPI` | 歌曲/成绩/别名 | `Authorization`（dev_key） | 同上 | ❌ 无代理 | `success` 字段判断 | 无 |
| Lxns OAuth | `lxns_client.py` | token 交换/刷新/查询 | Bearer / X-User-Token | 同上 | ❌ 无代理 | `success` 字段 | 无 |
| maimai-py | `qr_sync.py` `QRSyncService` | 二维码同步 | Import-Token / LXNS creds | `timeout` 参数 | ✅ 传 `http_proxy` | `describe_error` 映射 | 无 |
| SGWCMAID 解析 | `qr_sync.py` | SGID 提取/校验/新鲜度 | 无 | — | — | 返回 None/错误串 | — |
| WebSocket alias push | `command/alias.py` `AliasPushService` | 别名变更通知 | UUID 拼进 URL | 无显式超时 | ❌ | catch + 60s 重连 | 无 |

### 关键问题

- **所有 HTTP 客户端都没有真正使用 `http_proxy` 作为 aiohttp 代理**（`api_client.py`/`lxns_client.py` 完全不传 `proxy` 参数）。
- `MaimaiAPI.configure(proxy=...)` 的 `proxy` 参数是 `bool`，实际语义是「是否走 proxy.yuzuchan.site 反代」而非「HTTP 代理」。
- Lxns `_get`/`_user_get` 无代理、无 token 401 重试逻辑。

---

## 0.5.4 数据流

```
AstrBot Event
  ↓
main.py @command 装饰器路由（前缀命令）
  ├── _route_b50 / _route_minfo   → 查分统一路由
  ├── _on_message (EventMessageType.ALL) → 自然语言/正则监听
  ↓
command/<module>.py handler（async generator，yield 结果）
  ↓
MusicDataManager / ChuDataManager / UserStore / GroupConfigStore
  ↓
MaimaiAPI / LxnsAPI / QRSyncService（aiohttp / maimai-py）
  ↓
MessageEventResult（Markdown 文本 / base64 图片）
```

### 路由细节

- 游戏路由：`_resolve_game()` = 个人 `game_mode` > 群默认 > `maimai`。
- 查分器路由：`_get_prober()` = 群级 `prober` 配置，默认 maimai→divingfish、chunithm→lxns。
- Lxns token 通过 `self.lxns._user_token` 直接注入（绕过封装，存在并发脏写风险，见 1.7）。
- 数据加载失败后**没有 readiness 标记**，命令一律表现为「未找到」或空结果（见 1.2）。

---

## 0.5.5 生命周期

```
__init__()                     # 纯同步：实例化各 manager / store / client
  ↓
initialize()                   # 异步：configure API → load 数据 → 启动 alias push → 初始化 QR → 验证 token
  ├── music_data.load_all()    # 失败仅 log.error，继续
  ├── chu_data.load_all()      # 失败仅 log.error，继续
  ├── alias_push.start()       # 仅 enable_alias_push && uuid
  ├── QRSyncService()          # maimai-py 缺失则 warning，继续
  └── _validate_lxns_tokens()  # 刷新+验证，401 清除
  ↓
事件循环（@command / @event_message_type）
  ↓
terminate()                    # stop alias push → close api → close lxns
```

### 问题

- `initialize()` 中数据加载失败后仍打印「插件已加载」，无 readiness 状态。
- `_qr_sync.close()` 从未在 `terminate()` 中调用（资源泄漏，maimai-py client 不关闭）。
- `terminate()` 未等待后台 task（`_pending_oauth`/`_pending_df`/`_pending_sync` 的 `asyncio.create_task`）完成。

---

## 0.5.6 TODO / 半成品

### 显式 TODO / FIXME

| 位置 | 内容 |
|------|------|
| `command/alias.py:308` | `# TODO: 遍历群列表并发送`（alias push 未真正广播） |
| `command/mai_score.py` | B50 图片版已实现（`render/b50.py` + `cover.py`） |

### README 宣称支持但实际半成品/未实现

| README 描述 | 实际状态 |
|------------|---------|
| 「CHUNITHM 牌桌/进度」🚧 | 已标 🚧，实际无实现 |
| 「CHUNITHM 别名投票」🚧 | 已标 🚧，实际无实现 |
| 「图片版分表」✅ | maimai `b50` 已实现图片版（B30 待做），失败自动回退 Markdown |
| 「猜歌游戏」✅ | 可用，但 `enable_guess_game` 配置未生效 |

### 实际存在但 README 未写

| 功能 | 位置 |
|------|------|
| 分数线计算 `mailine` | 有，README 已列 |
| 随机选歌（`来/随/给个`） | 有，README 已列 |
| `syncdata` 二维码同步 | 有，README 已列 |

---

## 0.5.7 一致性检查

| 项 | 值 | 状态 |
|----|----|------|
| `metadata.yaml` version | `0.2.2` | 与 CHANGELOG 最新一致 |
| `main.py @register` version | `0.1.0` | ❌ **不一致**（应统一，正确值待定，暂不假设） |
| README 功能状态表 | ✅/🚧/❌ 基本准确 | ✅ |
| CHANGELOG 最新 | `0.2.2` | ✅ |
| `requirements.txt` `maimai-py==1.4.3` | 锁定 | ✅ |
| `astrbot_version` | `>=4.5.2` | 未验证运行环境 |

---

## 附：已知高优先级问题清单（进入 Phase 1 的修复顺序）

1. `http_proxy` 未按 HTTP Proxy 语义使用（`api_client.py`/`lxns_client.py`）。
2. `mai_rise_score_handler()` 成绩→谱面匹配风险（遍历 `music.ds` 而非锁定 `level_index`）。
3. `mai_level_progress_handler()` 解析 `rank_str` 后未参与过滤，且**无路由**。
4. 数据加载失败后无 readiness 状态。
5. `GroupConfigStore.set_group_game_mode/set_prober` 的 read-modify-write 无锁（`get_group_game_mode/get_prober` 直读文件）。
6. Lxns token 刷新：`_get_lxns_token()` 每次业务命令无条件 refresh。
7. async generator / `await` / `return` 结构 —— 已系统性复查（1.8）：无 `await async_generator()`、无 async generator `return <value>` 吞输出、所有 `async for` 目标均含 `yield`。✅
8. `metadata.yaml` 0.2.2 vs `@register` 0.1.0。
9. `ginfo` 仍用 base64 路径 —— 已修复：`image_to_base64()` 改为返回原始 base64（不含 `base64://`），消除与 `base64_image()` 的重复前缀 bug（根因经 AstrBot 4.28.2 源码确认：`Image.fromBase64` 内部拼前缀）。✅
10. alias push WebSocket 未广播 —— 已修复：新增 `alias_push_sessions` 映射存储 + `_broadcast()`，开启推送时记录 `unified_msg_origin`，广播时 `context.send_message(session, MessageChain)`。注意 `qq_official` 平台不支持主动发送。✅
