import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ChatType, ChatAction

import db.store as store
from bot import brain, memory

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
    reply = await brain.ask(message.chat.id, message.text)
    await message.answer(reply)
