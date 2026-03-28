#!/usr/bin/env python3
"""
KingoAds - @KingoAds_Bot
Kripto ödemeli Telegram fotoğraflı reklam yayın sistemi
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import Database
from handlers import common, admin, advertiser, channel_owner
from services.scheduler import AdScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("kingoads.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    config = Config()
    db = Database(config.DB_PATH)
    await db.init()
    logger.info("✅ Veritabanı hazır")

    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    scheduler = AdScheduler(bot, db, config)

    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(advertiser.router)
    dp.include_router(channel_owner.router)

    # Middleware ile db/config/scheduler inject
    dp["db"] = db
    dp["config"] = config
    dp["scheduler"] = scheduler

    logger.info("🚀 KingoAds @KingoAds_Bot başlatılıyor...")
    asyncio.create_task(scheduler.run())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
