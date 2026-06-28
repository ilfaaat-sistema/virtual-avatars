import asyncio
import logging
import shutil

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
import db.store as store
from bot import persona_kb
from bot.handlers import router as handlers_router
from bot.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _ensure_ffmpeg() -> None:
    """Resolve (and warm up) the ffmpeg binary at startup so failures surface
    loudly in the worker logs rather than on the first video job."""
    try:
        from video.ffmpeg_bin import get_ffmpeg
        logger.info("ffmpeg: using %s", get_ffmpeg())
    except Exception as e:
        logger.error("ffmpeg NOT available — video processing will fail: %s", e)


def _ensure_identity() -> None:
    """На Render папка identity/ пустая (gitignored). Если задан IDENTITY_IMAGE_B64 —
    декодируем фото лица в IDENTITY_DIR/master.jpg, чтобы Veo мог взять референс."""
    import base64

    if not config.IDENTITY_IMAGE_B64:
        return
    config.IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    target = config.IDENTITY_DIR / "master.jpg"
    if target.exists() and target.stat().st_size > 0:
        return
    try:
        target.write_bytes(base64.b64decode(config.IDENTITY_IMAGE_B64))
        logger.info("identity: фото лица записано → %s (%d байт)", target, target.stat().st_size)
    except Exception as e:
        logger.warning("identity: не удалось декодировать IDENTITY_IMAGE_B64: %s", e)


def cleanup_tmp() -> None:
    tmp = config.DATA_DIR / "tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    _ensure_ffmpeg()
    _ensure_identity()
    cleanup_tmp()
    await store.init_db()
    persona_kb.load()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(admin_router)   # admin handlers first (document upload etc.)
    dp.include_router(handlers_router)

    from bot.jobs import start_worker
    await start_worker(bot)

    logger.info("Bot starting — polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
