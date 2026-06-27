from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import config
import db.store as store

logger = logging.getLogger(__name__)

_WORKER_CONCURRENCY = 2   # max parallel Veo jobs (avoid Veo rate limits)
_STALE_MINUTES = 10       # processing jobs older than this → re-queue on startup
_POLL_INTERVAL = 5        # seconds between queue checks


async def enqueue(chat_id: int, mode: str, scene_prompt: str, spoken_line: str) -> int:
    """Put a video job in the queue. Returns job id."""
    job_id = await store.enqueue_video_job(chat_id, mode, scene_prompt, spoken_line)
    logger.info("jobs: поставлена задача id=%d chat=%d mode=%s", job_id, chat_id, mode)
    return job_id


async def _check_daily_limit(chat_id: int) -> bool:
    """True if user has NOT exceeded their daily video limit."""
    count = await store.get_video_count_today(chat_id)
    return count < config.VIDEO_DAILY_LIMIT_PER_USER


async def _find_cached_clip() -> str | None:
    """Return path to a cached clip from video_clips/ or None."""
    clips_dir = config.VIDEO_CLIPS_DIR
    if not clips_dir.exists():
        return None
    clips = sorted(clips_dir.glob("*.mp4"))
    return str(clips[0]) if clips else None


async def _process_job(job: dict, bot) -> None:
    """Full pipeline for one video job: Veo → compose → postprocess → sendVideoNote."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    mode = job["mode"]
    scene_prompt = job["scene_prompt"] or "нейтральный домашний фон, тёплый свет"
    spoken_line = job["spoken_line"] or ""

    raw_mp4 = muxed_mp4 = final_mp4 = None

    try:
        from video import get_provider
        from video import compose, postprocess

        provider = get_provider()

        # Step A: Generate video via Veo
        raw_mp4 = await provider.generate_scene(
            scene_prompt=scene_prompt,
            identity_images=[],
            talking=(mode == "talking"),
            spoken_line=spoken_line if mode == "talking" else None,
            duration_sec=config.VIDEO_TARGET_DURATION,
        )

        # Step B: Mux ElevenLabs voice over video
        muxed_mp4 = await compose.add_voice(raw_mp4, spoken_line)

        # Step C: Crop to 640×640 for Telegram
        final_mp4 = await postprocess.process(muxed_mp4)

        # Step D: Send as video note
        from aiogram.types import FSInputFile
        await bot.send_video_note(
            chat_id=chat_id,
            video_note=FSInputFile(final_mp4),
        )

        await store.update_video_job_status(job_id, "done")
        await store.increment_video_count(chat_id)
        logger.info("jobs: id=%d готово → отправлен кружочек", job_id)

    except Exception as e:
        logger.error("jobs: id=%d ошибка: %s", job_id, e, exc_info=True)
        await store.update_video_job_status(job_id, "failed", error=str(e)[:500])
        # Fallback: notify user that video failed
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="Не получилось записать кружочек 😔 Отвечаю голосом.",
            )
            from bot.voice import tts
            from aiogram.types import BufferedInputFile
            if spoken_line:
                ogg = await tts(spoken_line)
                if ogg:
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=BufferedInputFile(ogg, filename="voice.ogg"),
                    )
        except Exception as fb_err:
            logger.error("jobs: fallback для id=%d тоже упал: %s", job_id, fb_err)

    finally:
        # Clean up temp files
        for path in (raw_mp4, muxed_mp4):
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except OSError:
                    pass
        # final_mp4 is kept briefly for send, then cleaned up
        if final_mp4 and Path(final_mp4).exists():
            try:
                Path(final_mp4).unlink()
            except OSError:
                pass


async def _worker_loop(bot) -> None:
    """Async worker: continuously polls for queued jobs and processes them."""
    semaphore = asyncio.Semaphore(_WORKER_CONCURRENCY)

    async def run_with_semaphore(job: dict) -> None:
        async with semaphore:
            await _process_job(job, bot)

    logger.info("jobs: воркер запущен (concurrency=%d)", _WORKER_CONCURRENCY)
    while True:
        try:
            job = await store.take_next_video_job()
            if job:
                asyncio.create_task(run_with_semaphore(job))
            else:
                await asyncio.sleep(_POLL_INTERVAL)
        except Exception as e:
            logger.error("jobs: ошибка в воркер-цикле: %s", e)
            await asyncio.sleep(_POLL_INTERVAL)


async def start_worker(bot) -> None:
    """
    Initialize: recover stale jobs from previous run, then start the worker loop.
    Call once at bot startup.
    """
    await store.fail_stale_jobs(older_than_minutes=_STALE_MINUTES)
    asyncio.create_task(_worker_loop(bot))
    logger.info("jobs: воркер инициализирован")
