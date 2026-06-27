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

ВАЖНО: при [FORMAT:voice] отвечай максимально коротко — не более 2-3 предложений (до 400 символов).
Голос — это живой разговор, а не лекция. Длинный ответ голосом неудобен.

При [FORMAT:video] СРАЗУ ПОСЛЕ тега (до основного текста) добавь служебный блок:
mode=lifestyle   ← или talking
scene=<локация/действие одной строкой, ≤120 симв>
spoken_line=<реплика или закадровый текст, ≤250 симв>
---
<основной текст ответа пользователю — придёт сразу, пока снимается видео>

Правила выбора mode:
- lifestyle — владелец в локации (кафе, машина, улица), НЕ говорит в камеру, закадровый голос. По умолчанию.
- talking — короткий ответ прямо в камеру, ≤6 секунд речи.
spoken_line — ЧТО произносит голос в видео (для lifestyle это закадр, для talking — реплика в камеру). Всегда по-русски, ≤250 символов.
Если пользователь не указал локацию — scene="нейтральный домашний фон, тёплый свет".

Пример [FORMAT:video]:
[FORMAT:video]
mode=lifestyle
scene=кафе у окна, тёплый свет, задумчиво смотрит на улицу
spoken_line=Контент-воронки — это система, где одно вытекает из другого. Сначала ниша, потом личность, потом продукт.
---
Контент-воронка строится от ниши к продукту: сначала ты определяешь аудиторию, затем показываешь экспертность, и только потом предлагаешь купить.
"""


def _get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


def _parse_format(raw: str) -> tuple[str, str, dict]:
    """
    Вырезает [FORMAT:xxx] из первой строки.
    Для video — дополнительно парсит служебный блок (mode/scene/spoken_line).
    Возвращает (format, чистый_текст, meta_dict).
    """
    first_line, _, rest = raw.partition("\n")
    first_line = first_line.strip()
    if not (first_line.startswith("[FORMAT:") and first_line.endswith("]")):
        return "text", raw.strip(), {}

    fmt = first_line[8:-1].lower()
    if fmt not in ("text", "voice", "video"):
        fmt = "text"

    if fmt != "video":
        return fmt, rest.strip(), {}

    # Parse video meta block: key=value lines until "---" or blank line
    meta: dict = {}
    lines = rest.split("\n")
    reply_lines_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---":
            reply_lines_start = i + 1
            break
        if "=" in stripped and not stripped.startswith("#"):
            key, _, val = stripped.partition("=")
            meta[key.strip()] = val.strip()
        elif stripped == "" and meta:
            reply_lines_start = i + 1
            break

    reply_text = "\n".join(lines[reply_lines_start:]).strip()

    # Apply defaults
    meta.setdefault("mode", "lifestyle")
    meta.setdefault("scene", "нейтральный домашний фон, тёплый свет")
    meta.setdefault("spoken_line", reply_text[:250])

    if meta["mode"] not in ("lifestyle", "talking"):
        meta["mode"] = "lifestyle"

    return "video", reply_text, meta


async def ask(chat_id: int, user_text: str, voice_input: bool = False) -> tuple[str, str, dict]:
    """Возвращает (format, reply, meta). format: 'text' | 'voice' | 'video'. meta непустой только для video."""
    lock = _get_lock(chat_id)
    if lock.locked():
        return "text", "Подожди, я ещё думаю над предыдущим вопросом...", {}

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
                fmt, reply, meta = _parse_format(raw_reply)
                # Сохраняем оригинальный текст пользователя (без метки) и чистый ответ
                await memory.save_turn(chat_id, user_text, reply)
                return fmt, reply, meta
            except anthropic.APIError as e:
                if attempt == 0:
                    logger.warning("Anthropic API error (будет повтор): %s", e)
                    await asyncio.sleep(1)
                else:
                    logger.error("Anthropic API error (финальный): %s", e)
                    return "text", "Произошла ошибка при обращении к ИИ. Попробуй ещё раз.", {}
