import os
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8169988545:AAEk8jMumU9Lt2r4eXAn_iCp-4hSZe5YkLs")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not provided. Set environment variable BOT_TOKEN.")
    raise SystemExit(1)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

import db
import handlers

dp.include_router(handlers.router)

handlers.bot = bot
handlers.dp = dp

@dp.startup.register
async def on_startup():
    logger.info("Starting bot...")
    await db.init_db_and_seed()
    logger.info("Bot started, DB ready.")

@dp.shutdown.register
async def on_shutdown():
    logger.info("Shutting down bot...")
    await bot.session.close()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user, exiting...")
