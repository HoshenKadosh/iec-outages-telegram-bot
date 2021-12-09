from typing import Union
from aiogram import types
from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher import Dispatcher
from bot.config import config


class AdminFilter(BoundFilter):
    """
    Check if the user is a bot admin
    """

    key = "is_admin"

    def __init__(self, is_admin: bool):
        self.is_admin = is_admin

    async def check(self, obj: Union[types.Message, types.CallbackQuery]):
        user = obj.from_user
        if user.id in config.bot.admin_user_ids:
            return self.is_admin is True
        return self.is_admin is False


def bind_all_filters(dp: Dispatcher):
    dp.filters_factory.bind(
        AdminFilter,
    )
