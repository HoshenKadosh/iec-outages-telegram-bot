import asyncio
import logging
from aiogram.bot.bot import Bot
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types.bot_command import BotCommand
from aiogram.types.bot_command_scope import BotCommandScopeDefault
import bot.middlewares as middlewares
from bot.handlers import register_handlers
from bot.filters import bind_all_filters
from bot.iec.moitor_outages import OutagesMonitor
from bot.iec.api import iec_api
from tortoise import Tortoise
from bot.config import config
import os
import time


async def init_db(tz: str):
    DB_URL = "sqlite://bot/db/data/db.sqlite3"
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["bot.db.models"]},
        use_tz=True,
        timezone=tz,
    )
    await Tortoise.generate_schemas()

    async def log_db_queryies():
        conn_wrapper = Tortoise.get_connection("default")
        await conn_wrapper._connection.set_trace_callback(logging.debug)

    if not config.is_production:
        await log_db_queryies()


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(
            command="addresses_menu", description="כתובות לעדכונים, הוספה ומחיקה"
        ),
        BotCommand(
            command="check_address", description="בדיקת הפסקת חשמל בכתובת ספציפית"
        ),
        BotCommand(command="cancel", description="ביטול כל פעולה"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main():
    # set timezone\
    TIMEZONE = "Asia/Jerusalem"
    os.environ["TZ"] = TIMEZONE
    time.tzset()

    loggin_level = logging.WARN if config.is_production else logging.INFO
    logging.basicConfig(
        level=loggin_level,
        format="%(asctime)s - %(name)s - %(levelname)s: %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    )

    await init_db(TIMEZONE)
    bot = Bot(
        token=config.bot.token,
        parse_mode=types.ParseMode.HTML,
    )
    await set_bot_commands(bot)

    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    dp.middleware.setup(LoggingMiddleware())
    bind_all_filters(dp)
    register_handlers(dp)
    dp.middleware.setup(middlewares.UserMiddleware())

    outages_onitor = OutagesMonitor(bot)

    asyncio.ensure_future(outages_onitor.start_monitoring())

    try:
        await dp.skip_updates()
        await dp.start_polling()
    finally:
        # db and other things
        await Tortoise.close_connections()
        outages_onitor.stop_monitoring()
        await iec_api.session.close()
        await dp.storage.close()
        await dp.storage.wait_closed()
        session = await bot.get_session()
        await session.close()


try:
    asyncio.run(main())
except (KeyboardInterrupt, SystemError):
    exit()
