"""猜歌游戏：猜歌、猜曲绘、重置猜歌、开关。"""

from __future__ import annotations

import asyncio
import random
import secrets
from typing import TYPE_CHECKING, Any

from ..image_utils import image_to_base64, music_picture_path
from ..music_data import MusicDataManager

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


def _pick_guess_data(data_mgr: MusicDataManager) -> dict | None:
    """随机选一首热门歌曲生成猜歌数据。"""
    if not data_mgr.guess_data:
        return None
    music = secrets.choice(data_mgr.guess_data)
    aliases = data_mgr.get_aliases_for_music(music.id)
    answer = list(aliases) + [str(music.id), music.title]

    options = random.sample([
        f"的 Expert 难度是 {music.level[2]}" if len(music.level) > 2 else f"的难度是 {music.level[-1]}",
        f"的 Master 难度是 {music.level[3]}" if len(music.level) > 3 else f"的类型是 {music.type}",
        f"的分类是 {music.basic_info.genre}",
        f"的版本是 {music.basic_info.version}",
        f"的艺术家是 {music.basic_info.artist}",
        f"{'不' if music.type == 'SD' else ''}是 DX 谱面",
        f"{'没' if len(music.ds) == 4 else ''}有白谱",
        f"的 BPM 是 {music.basic_info.bpm}",
    ], 6)

    return {"music": music, "answer": answer, "options": options, "hint_index": 0}


async def guess_music_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """开始猜歌。"""
    group_id = event.get_group_id()
    if not group_id:
        yield event.plain_result("猜歌只能在群聊中使用。")
        return

    if data_mgr.guess_manager.is_active(group_id):
        yield event.plain_result("当前群已有猜歌进行中，请先回答或重置。")
        return

    data = _pick_guess_data(data_mgr)
    if not data:
        yield event.plain_result("猜歌数据未加载，请稍后再试。")
        return

    from ..models import GuessData
    music = data["music"]
    guess_obj = GuessData(music=music, img="", answer=data["answer"], end=False)
    data_mgr.guess_manager.set(group_id, guess_obj)

    # 存储额外数据
    data_mgr.guess_manager.active[group_id]._extra = data

    options = data["options"]
    hints = [
        f"🎵 猜歌开始！\n提示 1/7：这首歌的{options[0]}",
        f"提示 2/7：这首歌的{options[1]}",
        f"提示 3/7：这首歌的{options[2]}",
        f"提示 4/7：这首歌的{options[3]}",
        f"提示 5/7：这首歌的{options[4]}",
        f"提示 6/7：这首歌的{options[5]}",
    ]

    yield event.plain_result(hints[0])

    # 异步发送后续提示
    async def send_hints():
        for i in range(1, len(hints)):
            await asyncio.sleep(8)
            if not data_mgr.guess_manager.is_active(group_id):
                return
            try:
                await event.send(event.plain_result(hints[i]))
            except Exception:
                pass

        # 最后一个提示：裁切的封面图
        await asyncio.sleep(8)
        if not data_mgr.guess_manager.is_active(group_id):
            return
        try:
            from PIL import Image
            import numpy as np

            cover_path = music_picture_path(music.id, data_mgr._data_dir / "static" / "cover")
            im = Image.open(cover_path)
            w, h = im.size
            gray = np.array(im.convert("L"))
            freq = np.fft.fft2(gray)
            freq_shift = np.fft.fftshift(freq)
            magnitude = np.abs(freq_shift)
            weights = (magnitude / magnitude.max()) ** 2

            scale = random.uniform(0.15, 0.4)
            w2, h2 = int(w * scale), int(h * scale)
            top_p = min(1.3 - scale ** 0.4, 0.95) * 100
            flat = weights[:h - h2 + 1, :w - w2 + 1].flatten()
            threshold = np.percentile(flat, top_p)
            valid = np.where(flat >= threshold)[0]
            probs = flat[valid]
            probs /= probs.sum()
            idx = np.random.choice(valid, p=probs)
            cols = weights[:h - h2 + 1, :w - w2 + 1].shape[1]
            y, x = divmod(idx, cols)
            cropped = im.crop((x, y, x + w2, y + h2))

            b64 = image_to_base64(cropped)
            await event.send(event.make_result().message("提示 7/7：这是歌曲封面的一部分：").base64_image(b64))
        except Exception as e:
            logger.warning(f"发送封面裁切图失败: {e}")
            await event.send(event.plain_result("提示 7/7：（封面图生成失败）"))

    asyncio.create_task(send_hints())


async def guess_solve_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """猜歌答案匹配（在全局消息处理中调用）。"""
    group_id = event.get_group_id()
    if not group_id or not data_mgr.guess_manager.is_active(group_id):
        return False

    text = event.get_message_str().strip().lower()
    guess_data = data_mgr.guess_manager.get(group_id)
    if not guess_data:
        return False

    # 检查答案
    for ans in guess_data.answer:
        if text == ans.lower():
            music = guess_data.music
            data_mgr.guess_manager.end(group_id)
            yield event.plain_result(
                f"🎉 回答正确！答案是：{music.title} (ID:{music.id})"
            )
            return True

    return False


async def guess_pic_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """猜曲绘。"""
    group_id = event.get_group_id()
    if not group_id:
        yield event.plain_result("猜曲绘只能在群聊中使用。")
        return

    if data_mgr.guess_manager.is_active(group_id):
        yield event.plain_result("当前群已有猜歌进行中。")
        return

    if not data_mgr.guess_data:
        yield event.plain_result("猜歌数据未加载。")
        return

    music = secrets.choice(data_mgr.guess_data)
    aliases = data_mgr.get_aliases_for_music(music.id)
    answer = list(aliases) + [str(music.id), music.title]

    try:
        from PIL import Image
        import numpy as np

        cover_path = music_picture_path(music.id, data_mgr._data_dir / "static" / "cover")
        im = Image.open(cover_path)
        w, h = im.size
        gray = np.array(im.convert("L"))
        freq = np.fft.fft2(gray)
        weights = (np.abs(np.fft.fftshift(freq)) / np.abs(np.fft.fftshift(freq)).max()) ** 2
        scale = random.uniform(0.15, 0.4)
        w2, h2 = int(w * scale), int(h * scale)
        top_p = min(1.3 - scale ** 0.4, 0.95) * 100
        flat = weights[:h - h2 + 1, :w - w2 + 1].flatten()
        threshold = np.percentile(flat, top_p)
        valid = np.where(flat >= threshold)[0]
        probs = flat[valid]
        probs /= probs.sum()
        idx = np.random.choice(valid, p=probs)
        cols = weights[:h - h2 + 1, :w - w2 + 1].shape[1]
        y, x = divmod(idx, cols)
        cropped = im.crop((x, y, x + w2, y + h2))

        from ..models import GuessData
        guess_obj = GuessData(music=music, img=image_to_base64(cropped), answer=answer, end=False)
        data_mgr.guess_manager.set(group_id, guess_obj)

        b64 = image_to_base64(cropped)
        yield event.make_result().message("🎵 猜猜这是哪首歌的曲绘？30秒内回答！").base64_image(b64)

        # 30秒后自动结束
        async def auto_end():
            await asyncio.sleep(30)
            if data_mgr.guess_manager.is_active(group_id):
                data_mgr.guess_manager.end(group_id)
                try:
                    await event.send(event.plain_result(f"⏰ 时间到！答案是：{music.title} (ID:{music.id})"))
                except Exception:
                    pass

        asyncio.create_task(auto_end())

    except Exception as e:
        logger.exception("猜曲绘异常")
        yield event.plain_result(f"生成失败：{e}")


async def reset_guess_handler(
    event: AstrMessageEvent,
    data_mgr: MusicDataManager,
    **_: Any,
):
    """重置猜歌。"""
    group_id = event.get_group_id()
    if not group_id:
        return

    if data_mgr.guess_manager.is_active(group_id):
        music = data_mgr.guess_manager.get(group_id).music
        data_mgr.guess_manager.end(group_id)
        yield event.plain_result(f"已重置。答案是：{music.title} (ID:{music.id})")
    else:
        yield event.plain_result("当前群没有进行中的猜歌。")
