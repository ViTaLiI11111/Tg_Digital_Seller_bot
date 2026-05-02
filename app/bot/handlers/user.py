import stripe
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Document
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.database.models import User, Order, GlobalSettings
from app.bot.keyboards.reply import main_menu_keyboard
from app.bot.lexicon import MESSAGES, BUTTONS, STRIPE_PRODUCTS

user_router = Router()
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

async def is_payments_enabled(session: AsyncSession) -> tuple[bool, str]:
    stmt = select(GlobalSettings).where(GlobalSettings.id == 1)
    db_settings = await session.scalar(stmt)
    if not db_settings:
        return True, ""
    
    tz = ZoneInfo(settings.TIMEZONE)
    current_time = datetime.now(tz)
    
    # Helper to make datetime aware and convert to target TZ
    def localize_dt(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            # If naive, assume it's UTC and convert to local
            return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        else:
            return dt.astimezone(tz)

    logger.info(f"Checking payment status. Current time ({settings.TIMEZONE}): {current_time}")
    
    # Check custom schedule
    if db_settings.use_custom_schedule and db_settings.scheduled_disable_at and db_settings.scheduled_enable_at:
        start_tz = localize_dt(db_settings.scheduled_disable_at)
        end_tz = localize_dt(db_settings.scheduled_enable_at)
        
        logger.info(f"Custom schedule active. Start: {start_tz}, End: {end_tz}")

        if start_tz <= current_time < end_tz:
            logger.info("Result: DISABLED (inside custom schedule)")
            return False, "custom"
        elif current_time >= end_tz:
            logger.info("Result: ENABLING (custom schedule expired)")
            db_settings.use_custom_schedule = False
            db_settings.scheduled_disable_at = None
            db_settings.scheduled_enable_at = None
            db_settings.payments_enabled = True 
            await session.commit()
            return True, ""

    # Check manual/shabbat toggle
    if not db_settings.payments_enabled:
        if db_settings.auto_enable_at:
            auto_tz = localize_dt(db_settings.auto_enable_at)
            if current_time >= auto_tz:
                logger.info("Result: ENABLING (Shabbat auto-enable time passed)")
                db_settings.payments_enabled = True
                db_settings.auto_enable_at = None
                await session.commit()
                return True, ""
        logger.info("Result: DISABLED (manual toggle or Shabbat)")
        return False, "shabbat"

    logger.info("Result: ENABLED (default)")
    return True, ""

async def show_disclaimer(message: Message, session: AsyncSession, product_id: int):
    # This function shows the disclaimer OR processes the purchase immediately.
    # We MUST check if payments are enabled BEFORE processing the purchase if the user already accepted the disclaimer.
    
    user = await session.scalar(select(User).where(User.telegram_id == message.chat.id))
    
    if user and user.disclaimer_accepted:
        # If accepted, we jump straight to purchase logic. 
        # But we must check the schedule FIRST.
        enabled, reason = await is_payments_enabled(session)
        logger.info(f"User requested product {product_id}. Payments enabled: {enabled}")
        
        if not enabled:
            msg = MESSAGES['shabbat_message'] if reason == "shabbat" else MESSAGES['general_downtime_message']
            await message.answer(msg)
            return

        if product_id == 1:
            await process_buy_19(message, session)
        elif product_id == 2:
            await process_buy_39(message, session)
    else:
        # User has not accepted disclaimer. We don't check schedule here because
        # we only want to show the disclaimer. The schedule will be checked after they click accept.
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=BUTTONS['accept_disclaimer'], callback_data=f"accept_disclaimer_{product_id}")],
                [InlineKeyboardButton(text=BUTTONS['decline_disclaimer'], callback_data="decline_disclaimer")]
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
        # Check payments_enabled before allowing deep link to proceed
        enabled, reason = await is_payments_enabled(session)
        if not enabled:
            msg = MESSAGES['shabbat_message'] if reason == "shabbat" else MESSAGES['general_downtime_message']
            await message.answer(msg)
            return
            
        await show_disclaimer(message, session, 2)
        return

    await message.answer(
        MESSAGES['welcome'],
        reply_markup=main_menu_keyboard
    )

@user_router.message(F.text == BUTTONS['main_menu_product'])
async def product_handler(message: Message, session: AsyncSession):
    # CRITICAL FIX: Check payments enabled before proceeding with the main menu button
    enabled, reason = await is_payments_enabled(session)
    logger.info(f"User clicked product menu. Payments enabled: {enabled}")
    if not enabled:
        msg = MESSAGES['shabbat_message'] if reason == "shabbat" else MESSAGES['general_downtime_message']
        await message.answer(msg)
        return
        
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

    await callback.message.edit_reply_markup()

    # Now we check payment status before jumping into process_buy
    enabled, reason = await is_payments_enabled(session)
    logger.info(f"User accepted disclaimer for product {product_id}. Payments enabled: {enabled}")
    
    if not enabled:
        msg = MESSAGES['shabbat_message'] if reason == "shabbat" else MESSAGES['general_downtime_message']
        await callback.message.answer(msg)
        await callback.answer()
        return

    if product_id == 1:
        await process_buy_19(callback.message, session)
    elif product_id == 2:
        await process_buy_39(callback.message, session)

@user_router.callback_query(F.data == "decline_disclaimer")
async def decline_disclaimer_handler(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer(MESSAGES['disclaimer_declined'])
    await callback.answer()

async def process_buy_19(message: Message, session: AsyncSession):
    # Mandatory check before Stripe link generation
    enabled, reason = await is_payments_enabled(session)
    if not enabled:
        msg = MESSAGES['shabbat_message'] if reason == "shabbat" else MESSAGES['general_downtime_message']
        await message.answer(msg)
        return

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
    # Safety check
    enabled, reason = await is_payments_enabled(session)
    if not enabled:
        msg = MESSAGES['shabbat_message'] if reason == "shabbat" else MESSAGES['general_downtime_message']
        await message.answer(msg)
        return

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
