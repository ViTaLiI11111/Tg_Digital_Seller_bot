import stripe
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Document
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database.models import User, Order
from app.bot.keyboards.reply import main_menu_keyboard
from app.bot.lexicon import MESSAGES, BUTTONS, STRIPE_PRODUCTS

user_router = Router()

stripe.api_key = settings.STRIPE_SECRET_KEY

async def show_disclaimer(message: Message, session: AsyncSession, product_id: int):
    user = await session.scalar(select(User).where(User.telegram_id == message.chat.id))
    if user and user.disclaimer_accepted:
        if product_id == 1:
            await process_buy_19(message, session)
        elif product_id == 2:
            await process_buy_39(message, session)
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=BUTTONS['accept_disclaimer'], callback_data=f"accept_disclaimer_{product_id}")]
            ]
        )
        await message.answer(MESSAGES['disclaimer'], reply_markup=kb, parse_mode="HTML")

@user_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, command: CommandObject):
    stmt = select(User).where(User.telegram_id == message.chat.id)
    user = await session.scalar(stmt)

    if not user:
        user = User(
            telegram_id=message.chat.id,
            username=message.from_user.username,
            disclaimer_accepted=False
        )
        session.add(user)
        await session.commit()

    if command.args == "get_plan39":
        await show_disclaimer(message, session, 2)
        return

    await message.answer(
        MESSAGES['welcome'],
        reply_markup=main_menu_keyboard
    )

@user_router.message(F.text == BUTTONS['main_menu_product'])
async def product_handler(message: Message, session: AsyncSession):
    stmt = select(Order.product_id).where(
        Order.user_id == message.chat.id,
        Order.status == 'success'
    )
    result = await session.execute(stmt)
    purchased_products = [row[0] for row in result.fetchall()]

    if 1 not in purchased_products:
        await show_disclaimer(message, session, 1)
    elif 2 not in purchased_products:
        await show_disclaimer(message, session, 2)
    else:
        await message.answer(MESSAGES['all_purchased'], parse_mode="HTML")

@user_router.callback_query(F.data.startswith("accept_disclaimer_"))
async def accept_disclaimer_handler(callback: CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split("_")[-1])
    
    user = await session.scalar(select(User).where(User.telegram_id == callback.message.chat.id))
    if user:
        user.disclaimer_accepted = True
        await session.commit()

    await callback.message.delete()

    if product_id == 1:
        await process_buy_19(callback.message, session)
    elif product_id == 2:
        await process_buy_39(callback.message, session)

async def process_buy_19(message: Message, session: AsyncSession):
    # Коли викликається з accept_disclaimer_handler, message це callback.message
    # і chat.id тут потрібен, але user_id в Order має бути від chat.id (Telegram ID користувача)
    user_id = message.chat.id
    
    order = Order(
        user_id=user_id,
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
        success_url='https://t.me/Lady_Reset_bot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['pay_19'], url=checkout_session.url)]
        ]
    )
    await message.answer(
        MESSAGES['payment_link_1'],
        reply_markup=kb
    )

async def process_buy_39(message: Message, session: AsyncSession):
    user_id = message.chat.id

    order = Order(
        user_id=user_id,
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
        success_url='https://t.me/Lady_Reset_bot'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['pay_39'], url=checkout_session.url)]
        ]
    )
    await message.answer(
        MESSAGES['payment_link_2'],
        reply_markup=kb,
        parse_mode="HTML"
    )

@user_router.message(F.document)
async def get_file_id(message: Message):
    if message.chat.id in settings.ADMIN_IDS:
        doc: Document = message.document
        await message.answer(
            MESSAGES['file_id_info'].format(file_name=doc.file_name, file_id=doc.file_id),
            parse_mode="HTML"
        )
