from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог продуктів")],
        [KeyboardButton(text="ℹ️ Про проєкт"), KeyboardButton(text="📞 Підтримка")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Оберіть пункт меню..."
)
