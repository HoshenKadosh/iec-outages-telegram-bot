from aiogram import dispatcher
import bot.handlers.callbacks as callbacks
import bot.handlers.states as states
import bot.handlers.commands as commands


def register_handlers(dp: dispatcher):
    commands.register_cmds(dp)
    states.register_states_callbacks(dp)
    callbacks.register_callbacks(dp)
