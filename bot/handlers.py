import io
import logging
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile, FSInputFile
from aiogram.enums import ChatType, ChatAction

import config
import db.store as store
from bot import brain, memory, voice as voice_module

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return
    await store.upsert_user(
        message.chat.id,
        message.from_user.username if message.from_user else None,
        message.from_user.first_name if message.from_user else None,
    )

    # Check for a welcome clip in video_clips/
    welcome_clip = _find_welcome_clip()
    if welcome_clip:
        await message.answer_video_note(video_note=FSInputFile(welcome_clip))
        return

    await message.answer(
        "Привет! Я — виртуальный аватар. Задай мне любой вопрос или начни разговор."
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return
    await memory.reset(message.chat.id)
    await message.answer("История нашего разговора очищена.")


@router.message(F.text)
async def handle_text(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return

    await store.upsert_user(
        message.chat.id,
        message.from_user.username if message.from_user else None,
        message.from_user.first_name if message.from_user else None,
    )

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    fmt, reply, meta = await brain.ask(message.chat.id, message.text)
    await _send_by_format(message, fmt, reply, meta)


@router.message(F.voice)
async def handle_voice(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return

    await store.upsert_user(
        message.chat.id,
        message.from_user.username if message.from_user else None,
        message.from_user.first_name if message.from_user else None,
    )

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    tg_file = await message.bot.get_file(message.voice.file_id)
    buf: io.BytesIO = await message.bot.download_file(tg_file.file_path)
    voice_bytes = buf.read()

    recognized = await voice_module.stt(voice_bytes)
    if not recognized:
        await message.answer("Не удалось распознать голос, попробуй написать текстом.")
        return

    logger.info("STT распознал: %s", recognized[:80])

    fmt, reply, meta = await brain.ask(message.chat.id, recognized, voice_input=True)
    await _send_by_format(message, fmt, reply, meta)


def _find_welcome_clip() -> str | None:
    """Return path to a welcome clip (welcome*.mp4) from video_clips/, or None."""
    d = config.VIDEO_CLIPS_DIR
    if not d.exists():
        return None
    for pattern in ("welcome*.mp4", "приветствие*.mp4"):
        clips = sorted(d.glob(pattern))
        if clips:
            return str(clips[0])
    return None


def _find_cached_clip(mode: str) -> str | None:
    """Return path to any pre-made clip matching mode from video_clips/, or None."""
    d = config.VIDEO_CLIPS_DIR
    if not d.exists():
        return None
    clips = sorted(d.glob("*.mp4"))
    return str(clips[0]) if clips else None


async def _send_by_format(message: Message, fmt: str, reply: str, meta: dict) -> None:
    """Route response to the correct Telegram message type."""
    if fmt == "video":
        await _handle_video(message, reply, meta)
    elif fmt == "voice":
        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)
        ogg = await voice_module.tts(reply)
        if ogg:
            await message.answer_voice(voice=BufferedInputFile(ogg, filename="voice.ogg"))
            return
        await message.answer(reply)
    else:
        await message.answer(reply)


async def _handle_video(message: Message, reply: str, meta: dict) -> None:
    """
    For [FORMAT:video]:
    1. Check daily limit → if exceeded, reply by voice/text.
    2. Check video_clips/ cache → if hit, send immediately.
    3. Otherwise: send immediate text reply + "записываю кружочек…" + enqueue job.
    """
    chat_id = message.chat.id
    mode = meta.get("mode", "lifestyle")
    scene = meta.get("scene", "нейтральный домашний фон, тёплый свет")
    spoken_line = meta.get("spoken_line", reply[:250])

    # Daily limit check
    video_count = await store.get_video_count_today(chat_id)
    if video_count >= config.VIDEO_DAILY_LIMIT_PER_USER:
        logger.info("Лимит кружочков исчерпан для chat=%d (%d шт.)", chat_id, video_count)
        if reply:
            await message.answer(reply)
        ogg = await voice_module.tts("Лимит кружочков на сегодня исчерпан. Отвечаю голосом.")
        if ogg:
            await message.answer_voice(voice=BufferedInputFile(ogg, filename="voice.ogg"))
        else:
            await message.answer("Лимит кружочков на сегодня исчерпан.")
        return

    # Cached clip check
    cached = _find_cached_clip(mode)
    if cached:
        logger.info("Видео: отдаём кэшированный клип %s", cached)
        if reply:
            await message.answer(reply)
        await message.answer_video_note(video_note=FSInputFile(cached))
        return

    # No cache — generate via Veo
    if not config.VEO_API_KEY:
        # Graceful degradation: voice fallback if Veo not configured
        logger.warning("VEO_API_KEY не задан — отвечаем голосом")
        ogg = await voice_module.tts(spoken_line or reply)
        if ogg:
            await message.answer_voice(voice=BufferedInputFile(ogg, filename="voice.ogg"))
        else:
            await message.answer(reply)
        return

    # Send immediate text reply, then notify that video is being generated
    if reply:
        await message.answer(reply)
    await message.answer("🎥 Записываю кружочек, ~минуту…")

    from bot import jobs
    await jobs.enqueue(chat_id, mode, scene, spoken_line)
