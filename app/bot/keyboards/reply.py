from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from app.bot.lexicon import BUTTONS

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BUTTONS['main_menu_product'])],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт меню..."
)
