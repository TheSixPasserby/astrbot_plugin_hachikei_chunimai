"""command.admin AdminService 测试（fake store，不依赖 AstrBot）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrbot_plugin_hachikei_chunimai.command.admin import AdminService, _GAME_ALIASES, _PROBER_MAP


class _UserStore:
    def __init__(self): self.mode = {}
    async def set_game_mode(self, k, v): self.mode[k] = v
    def get_game_mode(self, k): return self.mode.get(k, "")


class _GroupStore:
    def __init__(self): self.game = {}; self.prober = {}
    async def set_group_game_mode(self, k, v): self.game[k] = v
    def get_group_game_mode(self, k): return self.game.get(k, "maimai")
    async def set_prober(self, game, prober, gid): self.prober[(game, gid)] = prober
    def get_prober(self, game, gid=None): return self.prober.get((game, gid), "divingfish")


class _MusicData:
    def __init__(self): self.music_list = [1]; self.alias_list = [1]; self._lxns = None
    def configure_alias(self, **kw): pass


class _ChuData:
    def __init__(self): self.songs = {1: 1}; self.aliases = {1: ["a"]}


def _make_svc():
    return AdminService(
        user_store=_UserStore(),
        group_store=_GroupStore(),
        config={},
        context=None,
        music_data=_MusicData(),
        chu_data=_ChuData(),
        get_qr_sync=lambda: None,
        is_admin=lambda e: True,
        group_id_of=lambda e: "g1",
        user_key_of=lambda e: "u1",
        message=lambda e, t: t,
    )


def test_game_alias_map():
    assert _GAME_ALIASES["舞萌"] == "maimai"
    assert _GAME_ALIASES["中二"] == "chunithm"
    assert _GAME_ALIASES["chunithm"] == "chunithm"


def test_prober_map():
    assert _PROBER_MAP["水鱼"] == "divingfish"
    assert _PROBER_MAP["落雪"] == "lxns"


def test_get_prober():
    svc = _make_svc()
    assert svc.get_prober(object(), "maimai") == "divingfish"
