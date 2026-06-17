import io
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ChatType, ChatAction

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
    fmt, reply = await brain.ask(message.chat.id, message.text)
    await _send_by_format(message, fmt, reply)


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

    # Скачиваем голосовое сообщение
    tg_file = await message.bot.get_file(message.voice.file_id)
    buf: io.BytesIO = await message.bot.download_file(tg_file.file_path)
    voice_bytes = buf.read()

    # STT
    recognized = await voice_module.stt(voice_bytes)
    if not recognized:
        await message.answer("Не удалось распознать голос, попробуй написать текстом.")
        return

    logger.info("STT распознал: %s", recognized[:80])

    fmt, reply = await brain.ask(message.chat.id, recognized, voice_input=True)
    await _send_by_format(message, fmt, reply)


async def _send_by_format(message: Message, fmt: str, reply: str) -> None:
    """Отправляет ответ в нужном формате. video → voice до Этапа 3."""
    if fmt in ("voice", "video"):
        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)
        ogg = await voice_module.tts(reply)
        if ogg:
            await message.answer_voice(
                voice=BufferedInputFile(ogg, filename="voice.ogg")
            )
            return
        # Fallback: отправить текстом
        suffix = " (голос временно недоступен)" if fmt == "voice" else ""
        await message.answer(reply + suffix)
    else:
        await message.answer(reply)
