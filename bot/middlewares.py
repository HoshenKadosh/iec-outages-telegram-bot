from aiogram.dispatcher.handler import current_handler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from bot.db.models import User


def prefetch_user(func):
    """Fetches the user from the db"""
    setattr(func, "userdata_required", True)
    return func


class UserMiddleware(BaseMiddleware):
    def __init__(self):
        super(UserMiddleware, self).__init__()

    @staticmethod
    async def get_user(telegram_id: int) -> User:
        handler = current_handler.get()
        if handler:
            attr = getattr(handler, "userdata_required", False)
            if not attr:
                return
        user = await User.filter(id=telegram_id).first()
        if user:
            return user
        return await User.create(id=telegram_id)

    async def on_process_message(self, message: Message, data: dict):
        data["user"] = await self.get_user(message.from_user.id)

    async def on_process_callback_query(
        self, callback_query: CallbackQuery, data: dict
    ):
        data["user"] = await self.get_user(callback_query.from_user.id)
