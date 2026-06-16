import asyncio
import logging

import anthropic

import config
from bot import persona_kb, memory

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

# One asyncio.Lock per chat_id prevents concurrent generations for the same chat
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


async def ask(chat_id: int, user_text: str) -> str:
    lock = _get_lock(chat_id)
    if lock.locked():
        return "Подожди, я ещё думаю над предыдущим вопросом..."

    async with lock:
        history = await memory.get_history(chat_id)

        persona = persona_kb.get_persona()
        kb = persona_kb.get_kb()

        # Two cache breakpoints: persona block + KB block.
        # Anthropic requires >= 2048 tokens per cached block for Sonnet.
        system: list[dict] = [
            {
                "type": "text",
                "text": persona,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if kb:
            system.append(
                {
                    "type": "text",
                    "text": f"# База знаний\n\n{kb}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        messages = history + [{"role": "user", "content": user_text}]

        for attempt in range(2):
            try:
                response = await _client.messages.create(
                    model=config.MODEL,
                    max_tokens=config.MAX_TOKENS,
                    system=system,
                    messages=messages,
                )
                reply = response.content[0].text
                usage = response.usage
                logger.debug(
                    "cache_creation=%d cache_read=%d input=%d output=%d",
                    getattr(usage, "cache_creation_input_tokens", 0),
                    getattr(usage, "cache_read_input_tokens", 0),
                    usage.input_tokens,
                    usage.output_tokens,
                )
                await memory.save_turn(chat_id, user_text, reply)
                return reply
            except anthropic.APIError as e:
                if attempt == 0:
                    logger.warning("Anthropic API error (will retry): %s", e)
                    await asyncio.sleep(1)
                else:
                    logger.error("Anthropic API error (final): %s", e)
                    return "Произошла ошибка при обращении к ИИ. Попробуй ещё раз."
