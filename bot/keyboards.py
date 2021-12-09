from aiogram import types
from bot.db.models import Address
import bot.handlers.callbacks.address_keyboard as address_kb
import bot.handlers.callbacks.cancel_any_state as cancel_state


def get_addresses_keyboard(
    addresses: list[Address], add_new_btn=False
) -> types.InlineKeyboardMarkup:
    """
    Generate keyboard with list of posts
    """
    markup = types.InlineKeyboardMarkup()
    if add_new_btn:
        markup.add(
            types.InlineKeyboardButton(
                "הוספת כתובת חדשה +",
                callback_data=address_kb.addresses_menu_cb.new(id=9, action="add_new"),
            ),
        )
    for add in addresses:
        markup.add(
            types.InlineKeyboardButton(
                f"{add.street.name} {add.home_num}, {add.city.name}",
                callback_data=address_kb.addresses_menu_cb.new(
                    id=add.id, action="view"
                ),
            ),
        )

    return markup


def get_view_address_keyboard(id: int) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "מחיקה",
            callback_data=address_kb.addresses_menu_cb.new(action="delete", id=id),
        ),
        types.InlineKeyboardButton(
            "« חזרה",
            callback_data=address_kb.addresses_menu_cb.new(action="list", id=id),
        ),
    )
    return markup


def get_cancel_state_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "ביטול",
            callback_data=cancel_state.cancel_any_state_cb.new(),
        ),
    )
    return markup


def get_back_to_menu_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "« חזרה",
            callback_data=address_kb.addresses_menu_cb.new(action="list", id=-1),
        ),
    )
    return markup
