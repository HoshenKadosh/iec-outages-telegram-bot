from aiogram import types, Dispatcher
from aiogram.dispatcher.storage import FSMContext
from aiogram.utils.callback_data import CallbackData

cancel_any_state_cb = CallbackData(
    "cancel_any_state",
)


async def cancel(call: types.CallbackQuery, state: FSMContext):
    state.get_state
    await state.finish()
    await call.answer("הפעולה בוטלה", False)


def register_callbacks(dp: Dispatcher):
    dp.register_callback_query_handler(cancel, cancel_any_state_cb.filter(), state="*")
