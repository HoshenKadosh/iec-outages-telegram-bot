from aiogram import types, Dispatcher
from aiogram.dispatcher.storage import FSMContext
from bot.db.models import Address, User
import bot.handlers.states.address_form as address_form
from bot.iec.cities_streets_downloader import download_and_fill_db_cities_streets
from bot.keyboards import get_addresses_keyboard
from bot.middlewares import prefetch_user


@prefetch_user
async def cmd_start(message: types.Message, user: User):
    first_name: str = message.chat.first_name or ""
    await message.answer(
        f"היי {first_name}\n"
        "בוט זה יאפשר לך לקבל הודעה בכל פעם שיש תקלה באספקת "
        "החשמל בכתובות שהוגדרו מראש.\n"
        "המידע נלקח מאתר חברת החשמל, "
        "ולכן לרוב יתפרסמו רק הפסקות שאורכן ארוך מ5 דקות.\n\n"
        "<b>פקודות:</b>\n"
        "תפריט כתובות לעדכונים, הוספה ומחיקה: /addresses_menu\n"
        "בדיקת תקינות אספקת החשמל בכתובת ספציפית: /check_address\n"
    )


@prefetch_user
async def cmd_addresses_menu(message: types.Message, user: User, edit_message=False):
    user_addresses = await Address.filter(user=user).select_related("city", "street")
    text = (
        "לחץ/י על הוספת כתובת חדשה כדי להוסיף כתובת, \n"
        "לחץ/י על כתובת להסרה/לצפיה בהיסטוריה"
    )
    kb = get_addresses_keyboard(user_addresses, add_new_btn=True)
    if edit_message:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(
            text,
            reply_markup=kb,
        )


async def cmd_check_address(message: types.Message, state: FSMContext):
    await address_form.start_address_form_one_time_check(message, state)
    pass


async def cmd_download_cities_streets(message: types.Message):
    await message.reply("מוריד ערים ורחובות, תהליך זה עלול לקחת מספר דקות...")
    try:
        added_cities, added_streets = await download_and_fill_db_cities_streets()
        await message.reply(
            "התהליך בוצע בהצלחה\n\n"
            f"ערים/ישובים שנוספו: {added_cities}\n"
            f"רחובות שנוספו: {added_streets}"
        )
    except Exception as e:
        await message.reply("אירעה שגיאה בעת תהליך ההורדה")
        print(str(e))


async def cmd_cancel_state(message: types.Message, state: FSMContext):
    cur_state = await state.get_state()
    if not cur_state:
        await message.answer("אין פעולה לבטל")
        return
    await state.finish()
    await message.answer("הפעולה בוטלה")


def register_cmds(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=["start", "help"])
    dp.register_message_handler(cmd_cancel_state, commands="cancel", state="*")
    dp.register_message_handler(cmd_addresses_menu, commands="addresses_menu")
    dp.register_message_handler(cmd_check_address, commands="check_address")
    dp.register_message_handler(
        cmd_download_cities_streets, commands="download_cities_streets", is_admin=True
    )
