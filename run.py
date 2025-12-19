# run.py
import os
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

# configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# set token via env or hardcode (not recommended to hardcode in production)
BOT_TOKEN = os.getenv("BOT_TOKEN", "здесь был токен")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not provided. Set environment variable BOT_TOKEN.")
    raise SystemExit(1)

# Bot + Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# import handlers and attach router + startup
import db
import handlers

# attach handlers' router to our dp
dp.include_router(handlers.router)

# make handlers module use the same bot/dispatcher instances
handlers.bot = bot
handlers.dp = dp

# register startup to init DB
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
