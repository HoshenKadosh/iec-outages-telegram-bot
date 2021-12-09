from datetime import datetime
from aiogram import types, Dispatcher
from bot.db.models import Address, Outage, User
from bot.handlers import commands
import bot.keyboards as kb
from bot.middlewares import prefetch_user
from aiogram.utils.callback_data import CallbackData
import bot.handlers.states.address_form as address_form

addresses_menu_cb = CallbackData("addresses_menu_cb", "id", "action")


@prefetch_user
async def add_new(call: types.CallbackQuery, user: User):
    if await address_form.start_address_form(call, user):
        await call.message.delete()


async def view(call: types.CallbackQuery, callback_data: dict[str, str]):
    await call.answer()
    add_id = callback_data.get("id")
    if not add_id:
        return
    add = await Address.filter(id=add_id).select_related("city", "street").first()

    if not add:
        return

    last_outage = (
        await Outage.filter(city=add.city, street=add.street, home_num=add.home_num)
        .order_by("start_time")
        .first()
        .only("start_time")
    )
    text = f"<b>{add.street.name} {add.home_num}, {add.city.name}</b>" "\n\n" + (
        f"הפסקת חשמל אחרונה: {datetime.strftime(last_outage.start_time, '%d/%m %H:%M')}"
        if last_outage
        else "לא נרשמו עדיין הפסקות חשמל במערכת"
    )
    await call.message.edit_text(
        text, reply_markup=kb.get_view_address_keyboard(add_id)
    )
    # asyncio.gather()


@prefetch_user
async def list(call: types.CallbackQuery, user: User):
    await call.answer()

    await commands.cmd_addresses_menu(call.message, user, True)


@prefetch_user
async def delete(call: types.CallbackQuery, callback_data: dict[str, str], user: User):
    add_id = callback_data.get("id")
    if not add_id:
        return
    add = await Address.filter(id=add_id, user=user).first()
    await add.delete()

    await call.answer("הכתובת נמחקה בהצלחה")
    await commands.cmd_addresses_menu(call.message, user, True)


def register_callbacks(dp: Dispatcher):
    dp.register_callback_query_handler(
        add_new, addresses_menu_cb.filter(action="add_new")
    )
    dp.register_callback_query_handler(view, addresses_menu_cb.filter(action="view"))
    dp.register_callback_query_handler(
        delete, addresses_menu_cb.filter(action="delete")
    )

    dp.register_callback_query_handler(list, addresses_menu_cb.filter(action="list"))
