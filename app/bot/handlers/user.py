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
        "👋 Добро пожаловать в Lady Reset! Выберите нужный раздел в меню ниже 👇",
        reply_markup=main_menu_keyboard
    )

@user_router.message(F.text == "🛍 Продукт")
async def product_handler(message: Message, session: AsyncSession):
    # Отримуємо всі успішні замовлення користувача
    stmt = select(Order.product_id).where(
        Order.user_id == message.from_user.id,
        Order.status == 'success'
    )
    result = await session.execute(stmt)
    purchased_products = [row[0] for row in result.fetchall()]

    kb = None
    text = ""

    if 1 not in purchased_products:
        # Юзер ще не купив перший продукт (19€)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Доступ (19€)", callback_data="buy_19")]
            ]
        )
        text = "Выберите продукт для покупки:\n\n<b>Доступ (19€)</b> — начало пути к вашему здоровью."
    elif 2 not in purchased_products:
        # Юзер купив перший, але не купив другий (39€)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="14 Lady Reset (39€)", callback_data="buy_39")]
            ]
        )
        text = "Вы уже приобрели базовый доступ. Переходите к следующему шагу:\n\n<b>14 Lady Reset — полная перезагрузка ЖКТ (39€)</b>"
    elif 3 not in purchased_products:
        # Юзер купив перший і другий, але не купив третій (89€)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Lady Reset PRO (89€)", callback_data="buy_89")]
            ]
        )
        text = "Вы прошли программу! Желаете большего?\n\n<b>Lady Reset PRO — Сопровождение (89€)</b>"
    else:
        # Юзер купив всі три продукти
        text = "Вы приобрели все доступные продукты! 🎉 Спасибо за доверие."

    if kb:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")

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
            [InlineKeyboardButton(text="Оплатить 19€", url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        "Супер! Для оплаты перейдите по ссылке ниже:",
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
            f"<i>(Скопируй этот file_id кликом и сохрани для кода)</i>",
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
            [InlineKeyboardButton(text="Оплатить 39€", url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        "🌟 <b>14 Lady Reset — полная перезагрузка ЖКТ (39€)</b>\n\nДля оплаты перейдите по ссылке ниже:",
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
            [InlineKeyboardButton(text="Оплатить 89€", url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        "👑 <b>Lady Reset PRO — Сопровождение (89€)</b>\n\nДля оплаты перейдите по ссылке ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()
