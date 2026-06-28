from __future__ import annotations

import asyncio
import logging
import uuid

import config

logger = logging.getLogger(__name__)

_el_client = None


def _get_client():
    global _el_client
    if _el_client is None:
        from elevenlabs import ElevenLabs
        _el_client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    return _el_client


def _tts_sync(text: str) -> bytes:
    client = _get_client()
    chunks = client.text_to_speech.convert(
        voice_id=config.ELEVENLABS_VOICE_ID,
        text=text,
        model_id=config.ELEVENLABS_MODEL_ID,
        output_format="opus_48000_128",
    )
    return b"".join(chunks)


def _stt_sync(file_path: str) -> str:
    client = _get_client()
    with open(file_path, "rb") as f:
        result = client.speech_to_text.convert(
            file=f,
            model_id="scribe_v2",
            language_code="ru",
        )
    return result.text or ""


async def tts(text: str) -> bytes | None:
    """ElevenLabs TTS → OGG/Opus bytes для Telegram. None если не сконфигурировано или ошибка."""
    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        logger.warning("ElevenLabs TTS не сконфигурирован (нет ELEVENLABS_API_KEY / VOICE_ID)")
        return None
    if len(text) > config.VOICE_MAX_CHARS:
        logger.debug("Текст длиннее %d символов — отправляем текстом", config.VOICE_MAX_CHARS)
        return None
    try:
        ogg_bytes = await asyncio.to_thread(_tts_sync, text)
        import db.store as store
        await store.log_usage("elevenlabs", chars=len(text))
        return ogg_bytes
    except Exception as e:
        logger.error("Ошибка TTS: %s", e)
        return None


async def stt(voice_data: bytes) -> str | None:
    """ElevenLabs Scribe STT. Принимает байты OGG-файла, возвращает распознанный текст или None."""
    if not config.ELEVENLABS_API_KEY:
        logger.warning("ElevenLabs STT не сконфигурирован (нет ELEVENLABS_API_KEY)")
        return None
    tmp_dir = config.DATA_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"voice_{uuid.uuid4().hex}.ogg"
    try:
        tmp_path.write_bytes(voice_data)
        text = await asyncio.to_thread(_stt_sync, str(tmp_path))
        return text.strip() if text else None
    except Exception as e:
        logger.error("Ошибка STT: %s", e)
        return None
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
