from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Продукт")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт меню..."
)
