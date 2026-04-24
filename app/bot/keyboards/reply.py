from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог продуктов")],
        [KeyboardButton(text="ℹ️ О проекте"), KeyboardButton(text="📞 Поддержка")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт меню..."
)
