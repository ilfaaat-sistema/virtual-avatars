from __future__ import annotations

import asyncio
import logging

import anthropic

import config
from bot import persona_kb, memory

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

# One asyncio.Lock per chat_id prevents concurrent generations for the same chat
_locks: dict[int, asyncio.Lock] = {}

_FORMAT_INSTRUCTIONS = """\
Перед каждым ответом ПЕРВОЙ строкой пиши тег формата (пользователь его не увидит — он будет вырезан):
[FORMAT:text]   — обычный текст (по умолчанию)
[FORMAT:voice]  — голосовое сообщение
[FORMAT:video]  — видео-кружочек

Правила выбора формата:
- По умолчанию всегда [FORMAT:text].
- Если сообщение пользователя начинается с метки «[ГОЛОСОВОЕ]» — используй [FORMAT:voice].
- Если пользователь явно просит ответить голосом или аудио — [FORMAT:voice].
- Если пользователь просит видео или кружочек — [FORMAT:video].
- Если пользователь явно называет другой формат — следуй его пожеланию.

Пример правильного ответа:
[FORMAT:text]
Контент-воронка — это путь, который проходит...
"""


def _get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


def _parse_format(raw: str) -> tuple[str, str]:
    """Вырезает [FORMAT:xxx] из первой строки. Возвращает (format, чистый_текст)."""
    first_line, _, rest = raw.partition("\n")
    first_line = first_line.strip()
    if first_line.startswith("[FORMAT:") and first_line.endswith("]"):
        fmt = first_line[8:-1].lower()
        if fmt not in ("text", "voice", "video"):
            fmt = "text"
        return fmt, rest.strip()
    # Claude не поставил тег — fallback
    return "text", raw.strip()


async def ask(chat_id: int, user_text: str, voice_input: bool = False) -> tuple[str, str]:
    """Возвращает (format, reply). format: 'text' | 'voice' | 'video'."""
    lock = _get_lock(chat_id)
    if lock.locked():
        return "text", "Подожди, я ещё думаю над предыдущим вопросом..."

    async with lock:
        history = await memory.get_history(chat_id)

        persona = persona_kb.get_persona()
        kb = persona_kb.get_kb()

        system: list[dict] = [
            {
                "type": "text",
                "text": _FORMAT_INSTRUCTIONS,
            },
            {
                "type": "text",
                "text": persona,
                "cache_control": {"type": "ephemeral"},
            },
        ]
        if kb:
            system.append(
                {
                    "type": "text",
                    "text": f"# База знаний\n\n{kb}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        # Голосовые сообщения получают метку — Claude видит контекст и выбирает [FORMAT:voice]
        user_msg_for_claude = f"[ГОЛОСОВОЕ]\n{user_text}" if voice_input else user_text
        messages = history + [{"role": "user", "content": user_msg_for_claude}]

        for attempt in range(2):
            try:
                response = await _client.messages.create(
                    model=config.MODEL,
                    max_tokens=config.MAX_TOKENS,
                    system=system,
                    messages=messages,
                )
                raw_reply = response.content[0].text
                usage = response.usage
                logger.debug(
                    "cache_creation=%d cache_read=%d input=%d output=%d",
                    getattr(usage, "cache_creation_input_tokens", 0),
                    getattr(usage, "cache_read_input_tokens", 0),
                    usage.input_tokens,
                    usage.output_tokens,
                )
                fmt, reply = _parse_format(raw_reply)
                # Сохраняем оригинальный текст пользователя (без метки) и чистый ответ
                await memory.save_turn(chat_id, user_text, reply)
                return fmt, reply
            except anthropic.APIError as e:
                if attempt == 0:
                    logger.warning("Anthropic API error (будет повтор): %s", e)
                    await asyncio.sleep(1)
                else:
                    logger.error("Anthropic API error (финальный): %s", e)
                    return "text", "Произошла ошибка при обращении к ИИ. Попробуй ещё раз."
