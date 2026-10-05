"""自然语言消息路由：猜歌答案、分数计算、运势、别名查歌等。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ..utils import is_group_message
from .chu_score import chu_alias_query_handler, chu_search_alias_handler
from .fun import daily_fortune_handler, mai_what_handler, random_song_handler
from .mai_guess import mai_guess_solve_handler
from .mai_score import mai_score_calc_handler, mai_score_line_handler
from .mai_search import mai_search_alias_handler
from .mai_table import (
    mai_level_progress_handler, mai_plate_progress_handler, mai_rise_score_handler,
    mai_rating_table_handler,
)
from .alias import alias_query_handler

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..api_client import MaimaiAPI
    from ..chu_data import ChuDataManager
    from ..lxns_client import LxnsAPI
    from ..mai_data import MusicDataManager


class NlpService:
    """自然语言路由服务：处理不带命令前缀的消息。"""

    def __init__(
        self,
        *,
        api: "MaimaiAPI",
        lxns: "LxnsAPI",
        music_data: "MusicDataManager",
        chu_data: "ChuDataManager",
        is_group_disabled,
        resolve_game,
        get_qq,
        get_df_token,
        get_lxns_token,
        get_prober,
        user_key_of,
        message,
    ) -> None:
        self.api = api
        self.lxns = lxns
        self.music_data = music_data
        self.chu_data = chu_data
        self._is_group_disabled = is_group_disabled
        self._resolve_game = resolve_game
        self._get_qq = get_qq
        self._get_df_token = get_df_token
        self._get_lxns_token = get_lxns_token
        self._get_prober = get_prober
        self._user_key_of = user_key_of
        self._message = message

    async def handle(self, event: "AstrMessageEvent"):
        """路由自然语言消息（不含账号/同步的 pending 监听，那部分由 main 处理）。"""
        if self._is_group_disabled(event):
            return
        try:
            if event.get_sender_id() == event.get_self_id():
                return
        except AttributeError:
            pass

        text = event.get_message_str().strip()
        game = self._resolve_game(event)

        # --- 仅 maimai 模式 ---

        if game == "maimai":
            # 猜歌答案
            if is_group_message(event):
                async for r in mai_guess_solve_handler(event, self.music_data):
                    yield r
                return

            # 分数计算：X的Y是多少分
            if re.match(r"^[\d.]+的[\d.]+是多少分$", text):
                async for r in mai_score_calc_handler(event, self.music_data):
                    yield r
                    return

            # 今日运势
            if re.match(r"^(今日mai|今日舞萌|今日运势)$", text):
                async for r in daily_fortune_handler(event, self.music_data):
                    yield r
                    return

            # mai什么 / 随机歌曲
            if re.match(r"^.*mai.*什么", text):
                async for r in mai_what_handler(event, self.music_data):
                    yield r
                    return

            # 来/随/给个 + 难度
            if re.match(r"^[来随给]个", text):
                async for r in random_song_handler(event, self.music_data):
                    yield r
                    return

            # 分数线
            if text.startswith("分数线"):
                async for r in mai_score_line_handler(event, self.music_data):
                    yield r
                    return

            # X定数表
            if re.match(r"^(?!更新).+?定数表$", text):
                async for r in mai_rating_table_handler(event, self.music_data):
                    yield r
                    return

            # 版牌进度 / 等级进度
            if re.search(r"进度\s*$", text):
                qq = self._get_qq(event)
                df_token = self._get_df_token(event)
                # 等级进度以数字开头（如 "12 SSS进度"），版牌进度以版本字开头（如 "真極进度"）
                if re.match(r"^\d", text):
                    async for r in mai_level_progress_handler(
                        event, self.api, self.music_data, qq=qq, token=df_token
                    ):
                        yield r
                    return
                async for r in mai_plate_progress_handler(
                    event, self.api, self.music_data, qq=qq, token=df_token
                ):
                    yield r
                return

            # 推分
            if re.match(r"^我要在", text):
                prober = self._get_prober(event, "maimai")
                lxns_token = await self._get_lxns_token(event)
                qq = self._get_qq(event)
                df_token = self._get_df_token(event)
                async for r in mai_rise_score_handler(
                    event, self.api, self.music_data, prober=prober,
                    lxns=self.lxns, lxns_token=lxns_token, qq=qq, token=df_token,
                ):
                    yield r
                return

        # --- 共用：别名相关（按游戏路由） ---

        if re.search(r"有什么别[名称]$", text):
            if game == "chunithm":
                async for r in chu_alias_query_handler(event, self.chu_data):
                    yield r
            else:
                async for r in alias_query_handler(event, self.music_data):
                    yield r
            return

        if re.search(r"(是什么歌|是啥歌)$", text):
            if game == "chunithm":
                async for r in chu_search_alias_handler(event, self.chu_data):
                    yield r
            else:
                async for r in mai_search_alias_handler(event, self.music_data):
                    yield r
            return
