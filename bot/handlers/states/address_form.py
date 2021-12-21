from aiogram import types
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.dispatcher.storage import FSMContext
from aiogram.types.message import Message
from bot.config import config
from bot.db.models import Address, City, Street, User
from bot.middlewares import prefetch_user
from aiogram.dispatcher.filters.state import State, StatesGroup
from bot.iec.api import iec_api
from bot.utils import detail_text_from_outage
from bot.keyboards import get_back_to_menu_keyboard


class AddressForm(StatesGroup):
    city = State()
    street = State()
    home_num = State()


@prefetch_user
async def start_address_form(query: types.CallbackQuery, user: User):
    user_addresses_count = await Address.filter(user=user).count()
    max = config.bot.max_addresses_for_user
    if user_addresses_count >= max:
        await query.answer(
            f"לא ניתן להוסיף יותר מ{max} כתובות.\nיש למחוק כתובת אחת ולנסות שוב",
            show_alert=True,
        )
        return False
    await query.message.answer("<b>הוספת כתובת לעדכונים</b>" "\nלביטול: /cancel")

    await query.message.answer(
        "מה שם העיר/יישוב?",
        # reply_markup=kb.get_cancel_state_keyboard(),
    )
    await AddressForm.city.set()
    return True


async def start_address_form_one_time_check(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data["one_time_check"] = True
    await message.answer("<b>בדיקת סטטוס הפסקת חשמל בכתובת</b>" "\nלביטול: /cancel")
    await message.answer(
        "מה שם העיר/יישוב?",
        # reply_markup=kb.get_cancel_state_keyboard(),
    )
    await AddressForm.city.set()
    return True


async def process_address_form_city(message: types.Message, state: FSMContext):
    name = message.text.strip()
    city = await City.filter(name=name).first()
    if not city:
        await message.reply(
            "העיר/יישוב שהוזן לא נמצא"
            "\nיש להזין את השם במלואו כפי שמופיע במאגר חברת החשמל.\n"
            "לדוגמה: מודיעין מכבים רעות, תל אביב יפו",
            # reply_markup=kb.get_cancel_state_keyboard(),
        )
        return

    async with state.proxy() as data:
        data["city"] = city

    await AddressForm.street.set()

    await message.answer(
        "מעולה! ועכשיו, מה שם הרחוב?",  # reply_markup=kb.get_cancel_state_keyboard()
    )


async def process_address_form_street(message: types.Message, state: FSMContext):
    name = message.text.strip()
    async with state.proxy() as data:
        street = await Street.filter(name=name, city=data["city"]).first()
    if not street:
        await message.reply(
            "הרחוב שהוזן לא נמצא",  # reply_markup=kb.get_cancel_state_keyboard()
        )
        return

    async with state.proxy() as data:
        data["street"] = street

    await AddressForm.home_num.set()

    await message.answer(
        "ולסיום, מה מספר הבניין?",  # reply_markup=kb.get_cancel_state_keyboard()
    )


async def address_form_home_not_num(message: types.Message):
    await message.reply(
        "מספר הבניין חייב להיות מספר בלבד, ללא כל תווים אחרים",
        # reply_markup=kb.get_cancel_state_keyboard(),
    )


@prefetch_user
async def process_address_form_home(
    message: types.Message, state: FSMContext, user: User
):
    num = message.text.strip()

    async with state.proxy() as data:
        home_num = int(num)
        city: City = data["city"]
        street: Street = data["street"]
        one_time_check: bool = data.get("one_time_check", False)

    full_address = f"{street.name} {home_num}, {city.name}"

    if one_time_check:
        await message.reply("נא להמתין...")
        try:
            outage_status = await iec_api.get_outage_for_address(
                city.id, city.district_id, street.id, home_num
            )
            if (
                not outage_status.is_active_incident
                and not outage_status.is_planned_outage
            ):
                await message.answer(f"לא ידוע כרגע על הפסקת חשמל ב{full_address}")
                return
            text = detail_text_from_outage(
                outage_status.get_outage_model(), full_address
            )
            await message.answer("ידוע כרגע על " + text)
        except Exception:
            message.answer("אירעה שגיאה בבדיקת הסטטוס. יש לנסות שוב מאוחר יותר")
        await state.finish()
        return

    address, _ = await Address.get_or_create(
        city=city,
        street=street,
        home_num=home_num,
        user=user,
    )

    await message.answer(
        "זהו!\n"
        "הכתובת "
        f"<b>{full_address}</b> "
        "התווספה.\n מרגע זה תקבל/י הודעה בעת הפסקת חשמל עם פירוט "
        "וצפי לסיום.\n"
        "בעת חזרת החשמל תתקבל הודעה נוספת.",
        reply_markup=get_back_to_menu_keyboard(),
    )

    await state.finish()


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(process_address_form_city, state=AddressForm.city)
    dp.register_message_handler(process_address_form_street, state=AddressForm.street)
    dp.register_message_handler(
        address_form_home_not_num,
        lambda message: not message.text.strip().isnumeric(),
        state=AddressForm.home_num,
    )
    dp.register_message_handler(
        process_address_form_home,
        lambda message: message.text.strip().isnumeric(),
        state=AddressForm.home_num,
    )
