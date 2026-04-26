import stripe
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Document, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database.models import User, Order
from app.bot.keyboards.reply import main_menu_keyboard
from app.bot.lexicon import MESSAGES, BUTTONS, STRIPE_PRODUCTS

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
        MESSAGES['welcome'],
        reply_markup=main_menu_keyboard
    )

@user_router.message(F.text == BUTTONS['main_menu_product'])
async def product_handler(message: Message, session: AsyncSession):
    stmt = select(Order.product_id).where(
        Order.user_id == message.from_user.id,
        Order.status == 'success'
    )
    result = await session.execute(stmt)
    purchased_products = [row[0] for row in result.fetchall()]

    kb = None
    text = ""

    if 1 not in purchased_products:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=BUTTONS['buy_19'], callback_data="buy_19")]
            ]
        )
        text = MESSAGES['product_1_offer']
    elif 2 not in purchased_products:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=BUTTONS['buy_39'], callback_data="buy_39")]
            ]
        )
        text = MESSAGES['product_2_offer']
    elif 3 not in purchased_products:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=BUTTONS['buy_89'], callback_data="buy_89")]
            ]
        )
        text = MESSAGES['product_3_offer']
    else:
        text = MESSAGES['all_purchased']

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
                    'name': STRIPE_PRODUCTS['name_1'],
                },
                'unit_amount': 1900,
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url='https://t.me/testtsettesttsettest_bot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['pay_19'], url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        MESSAGES['payment_link_1'],
        reply_markup=kb
    )
    await callback.answer()

@user_router.message(F.document)
async def get_file_id(message: Message):
    if message.from_user.id in settings.ADMIN_IDS:
        doc: Document = message.document
        await message.answer(
            MESSAGES['file_id_info'].format(file_name=doc.file_name, file_id=doc.file_id),
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
                    'name': STRIPE_PRODUCTS['name_2'],
                },
                'unit_amount': 3900,
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url='https://t.me/testtsettesttsettest_bot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['pay_39'], url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        MESSAGES['payment_link_2'],
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
                    'name': STRIPE_PRODUCTS['name_3'],
                },
                'unit_amount': 8900,
            },
            'quantity': 1,
        }],
        mode='payment',
        metadata={'order_id': str(order.id)},
        success_url='https://t.me/testtsettesttsettest_bot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['pay_89'], url=checkout_session.url)]
        ]
    )
    await callback.message.answer(
        MESSAGES['payment_link_3'],
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()
