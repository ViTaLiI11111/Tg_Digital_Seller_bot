import stripe
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Document, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database.models import User, Order
from app.bot.keyboards.reply import main_menu_keyboard

user_router = Router()

stripe.api_key = settings.STRIPE_SECRET_KEY

@user_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = await session.scalar(stmt)

    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        session.add(user)
        await session.commit()

    await message.answer(
        "👋 Вітаю у Lady Reset! Оберіть потрібний розділ у меню нижче 👇",
        reply_markup=main_menu_keyboard
    )

@user_router.message(F.text == "🛍 Каталог продуктів")
async def catalog_handler(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Доступ (19€)", callback_data="buy_19")],
            [InlineKeyboardButton(text="14 Lady Reset (39€)", callback_data="buy_39")],
            [InlineKeyboardButton(text="Lady Reset PRO (89€)", callback_data="buy_89")]
        ]
    )
    await message.answer(
        "Оберіть продукт для покупки:",
        reply_markup=kb
    )

@user_router.message(F.text == "ℹ️ Про проєкт")
async def about_project_handler(message: Message):
    await message.answer(
        "ℹ️ <b>Lady Reset</b> — це проєкт для повної перезавантаження та покращення вашого здоров'я.\n"
        "Тут ви знайдете матеріали, програми та супровід для досягнення найкращих результатів.",
        parse_mode="HTML"
    )

@user_router.message(F.text == "📞 Підтримка")
async def support_handler(message: Message):
    await message.answer(
        "📞 Якщо у вас виникли питання або проблеми з оплатою, зверніться до нашої підтримки: @admin_username"
    )

@user_router.callback_query(F.data == "buy_19")
async def process_buy_19(callback: CallbackQuery, session: AsyncSession):
    order = Order(
        user_id=callback.from_user.id,
        product_id=1,
        status='pending'
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': 'Доступ (19€)',
                },
                'unit_amount': 1900,
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url='https://t.me/LadyResetBot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатити 19€", url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        "Супер! Для оплати перейдіть за посиланням нижче:",
        reply_markup=kb
    )
    await callback.answer()

@user_router.message(F.document)
async def get_file_id(message: Message):
    if message.from_user.id in settings.ADMIN_IDS:
        doc: Document = message.document
        await message.answer(
            f"📄 <b>Файл:</b> {doc.file_name}\n"
            f"🔑 <b>file_id:</b> <code>{doc.file_id}</code>\n\n"
            f"<i>(Скопіюй цей file_id кліком і збережи для коду)</i>",
            parse_mode="HTML"
        )

@user_router.callback_query(F.data == "buy_39")
async def process_buy_39(callback: CallbackQuery, session: AsyncSession):
    order = Order(
        user_id=callback.from_user.id,
        product_id=2,
        status='pending'
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': '14 Lady Reset — полная перезагрузка ЖКТ (39€)',
                },
                'unit_amount': 3900,
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url='https://t.me/LadyResetBot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатити 39€", url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        "🌟 <b>14 Lady Reset — полная перезагрузка ЖКТ (39€)</b>\n\nДля оплати перейдіть за посиланням нижче:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@user_router.callback_query(F.data == "buy_89")
async def process_buy_89(callback: CallbackQuery, session: AsyncSession):
    order = Order(
        user_id=callback.from_user.id,
        product_id=3,
        status='pending'
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': 'Lady Reset PRO — Сопровождение (89€)',
                },
                'unit_amount': 8900,
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url='https://t.me/LadyResetBot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатити 89€", url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        "👑 <b>Lady Reset PRO — Сопровождение (89€)</b>\n\nДля оплати перейдіть за посиланням нижче:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()
