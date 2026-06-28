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
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        logger.info("ffmpeg: static binaries added to PATH")
    except ImportError:
        pass  # system ffmpeg used


def cleanup_tmp() -> None:
    tmp = config.DATA_DIR / "tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    _ensure_ffmpeg()
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
