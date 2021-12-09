from aiogram.dispatcher.dispatcher import Dispatcher
import bot.handlers.callbacks.address_keyboard as address_keyboard
import bot.handlers.callbacks.cancel_any_state as cancel_any_state


def register_callbacks(dp: Dispatcher):
    address_keyboard.register_callbacks(dp)
    cancel_any_state.register_callbacks(dp)
