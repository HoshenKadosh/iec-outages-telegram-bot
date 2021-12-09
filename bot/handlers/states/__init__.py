from aiogram.dispatcher.dispatcher import Dispatcher
import bot.handlers.states.address_form as address_form


def register_states_callbacks(dp: Dispatcher):
    address_form.register_handlers(dp)
