from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database.models import GlobalSettings
from app.bot.lexicon import MESSAGES, BUTTONS

# We must import the single source of truth for payment status
from app.bot.handlers.user import is_payments_enabled

admin_router = Router()

class AdminStates(StatesGroup):
    waiting_for_password = State()
    waiting_for_downtime_range = State()

async def get_global_settings(session: AsyncSession) -> GlobalSettings:
    stmt = select(GlobalSettings).where(GlobalSettings.id == 1)
    db_settings = await session.scalar(stmt)
    if not db_settings:
        db_settings = GlobalSettings(id=1, payments_enabled=True)
        session.add(db_settings)
        await session.commit()
        await session.refresh(db_settings)
    return db_settings

def get_admin_keyboard(payments_status: bool) -> InlineKeyboardMarkup:
    toggle_text = "🟢 Платежи включены" if payments_status else "🔴 Платежи выключены"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔄 {toggle_text}", callback_data="admin_toggle_payments")],
            [InlineKeyboardButton(text=BUTTONS['admin_enable_shabbat'], callback_data="admin_shabbat_menu")],
            [InlineKeyboardButton(text=BUTTONS['admin_custom_downtime'], callback_data="admin_custom_downtime_prompt")],
            [InlineKeyboardButton(text=BUTTONS['admin_refresh_status'], callback_data="admin_refresh_status")],
            [InlineKeyboardButton(text=BUTTONS['admin_close'], callback_data="admin_close")]
        ]
    )

async def build_admin_menu_text(session: AsyncSession, current_status: bool) -> str:
    db_settings = await get_global_settings(session)
    tz = ZoneInfo(settings.TIMEZONE)
    
    if current_status:
        status_text = "🟢 Включены"
    else:
        # Determine why it is disabled
        if db_settings.use_custom_schedule and db_settings.scheduled_disable_at and db_settings.scheduled_enable_at:
            current_time = datetime.now(tz)
            
            # Helper to make datetime aware and convert to target TZ
            def localize_dt(dt: datetime) -> datetime:
                if dt.tzinfo is None:
                    # If naive, assume it's UTC (as usually stored by SQLAlchemy DateTime(timezone=True) depending on driver)
                    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                else:
                    return dt.astimezone(tz)

            start_tz = localize_dt(db_settings.scheduled_disable_at)
            end_tz = localize_dt(db_settings.scheduled_enable_at)
            
            if start_tz <= current_time < end_tz:
                status_text = "🔴 Выключены (Автоматически - Свой период)"
            else:
                 status_text = "🔴 Выключены (Вручную)"
        elif db_settings.auto_enable_at:
            status_text = "🔴 Выключены (Автоматически - Шаббат)"
        else:
            status_text = "🔴 Выключены (Вручную)"

    text = f"{MESSAGES['admin_welcome']}\n\n{MESSAGES['admin_payments_status'].format(status=status_text)}"
    
    if db_settings.auto_enable_at and not db_settings.use_custom_schedule:
        # Helper to make datetime aware and convert to target TZ
        def localize_dt(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            else:
                return dt.astimezone(tz)
                
        auto_tz = localize_dt(db_settings.auto_enable_at)
        time_str = auto_tz.strftime("%Y-%m-%d %H:%M:%S")
        text += f"\n⏳ Авто-включение (Шаббат): <b>{time_str} ({settings.TIMEZONE})</b>"
    elif db_settings.use_custom_schedule and db_settings.scheduled_disable_at and db_settings.scheduled_enable_at:
        def localize_dt(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            else:
                return dt.astimezone(tz)
                
        start_tz = localize_dt(db_settings.scheduled_disable_at)
        end_tz = localize_dt(db_settings.scheduled_enable_at)
        start_str = start_tz.strftime("%Y-%m-%d %H:%M")
        end_str = end_tz.strftime("%Y-%m-%d %H:%M")
        text += f"\n⏳ Свой период отключения:\nС: <b>{start_str} ({settings.TIMEZONE})</b>\nПо: <b>{end_str} ({settings.TIMEZONE})</b>"
        
    return text

@admin_router.message(Command("secret_admin"))
async def secret_admin_command(message: Message, state: FSMContext):
    await message.answer(MESSAGES['admin_prompt_password'])
    await state.set_state(AdminStates.waiting_for_password)

@admin_router.message(StateFilter(AdminStates.waiting_for_password))
async def process_admin_password(message: Message, state: FSMContext, session: AsyncSession):
    if message.from_user.id in settings.ADMIN_IDS:
        if message.text == settings.ADMIN_PASSWORD:
            current_status, _ = await is_payments_enabled(session)
            text = await build_admin_menu_text(session, current_status)
            await message.answer(text, reply_markup=get_admin_keyboard(current_status), parse_mode="HTML")
            await state.clear()
        else:
            await message.answer(MESSAGES['admin_wrong_password'])
            await state.clear()
    else:
        await message.answer(MESSAGES['admin_wrong_password'])
        await state.clear()

@admin_router.callback_query(F.data == "admin_toggle_payments")
async def toggle_payments_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    db_settings = await get_global_settings(session)
    
    # Check what the current dynamic state is
    current_status, _ = await is_payments_enabled(session)
    
    # We toggle the manual flag based on the dynamic state
    db_settings.payments_enabled = not current_status
    db_settings.auto_enable_at = None 
    db_settings.use_custom_schedule = False
    await session.commit()
    
    new_status, _ = await is_payments_enabled(session)
    text = await build_admin_menu_text(session, new_status)
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_admin_keyboard(new_status),
        parse_mode="HTML"
    )
    await callback.answer("Статус платежей изменен")

@admin_router.callback_query(F.data == "admin_refresh_status")
async def refresh_status_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    current_status, _ = await is_payments_enabled(session)
    text = await build_admin_menu_text(session, current_status)
    
    try:
        await callback.message.edit_text(
            text, 
            reply_markup=get_admin_keyboard(current_status),
            parse_mode="HTML"
        )
        await callback.answer("Статус обновлен ✅")
    except Exception:
        # Catch exceptions like TelegramBadRequest: message is not modified
        await callback.answer("Статус не изменился", show_alert=False)

@admin_router.callback_query(F.data == "admin_shabbat_menu")
async def shabbat_menu_handler(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['shabbat_time_1'], callback_data="set_shabbat_sat_20")],
            [InlineKeyboardButton(text=BUTTONS['shabbat_time_2'], callback_data="set_shabbat_sun_09")],
            [InlineKeyboardButton(text=BUTTONS['admin_back_to_main'], callback_data="admin_main_menu")]
        ]
    )
    await callback.message.edit_text("Выберите время автоматического включения платежей после Шаббата:", reply_markup=kb)

@admin_router.callback_query(F.data.startswith("set_shabbat_"))
async def set_shabbat_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    # Shabbat times are calculated based on UTC, so let's stick to UTC for internal storage
    now = datetime.utcnow()
    
    if callback.data == "set_shabbat_sat_20":
        days_ahead = 5 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
        enable_time = target_date.replace(hour=20, minute=0, second=0, microsecond=0)
    elif callback.data == "set_shabbat_sun_09":
        days_ahead = 6 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
        enable_time = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        return

    db_settings = await get_global_settings(session)
    db_settings.payments_enabled = False
    
    # Store as explicitly UTC
    db_settings.auto_enable_at = enable_time.replace(tzinfo=ZoneInfo("UTC"))
    db_settings.use_custom_schedule = False
    await session.commit()

    # Re-evaluate the status and text to ensure the UI is updated immediately
    current_status, _ = await is_payments_enabled(session)
    text = await build_admin_menu_text(session, current_status)
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="admin_main_menu")]]
        ),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data == "admin_custom_downtime_prompt")
async def custom_downtime_prompt_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BUTTONS['admin_back_to_main'], callback_data="admin_cancel_downtime_prompt")]]
    )
    await callback.message.edit_text(MESSAGES['admin_custom_range_prompt'], reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_downtime_range)

@admin_router.callback_query(F.data == "admin_cancel_downtime_prompt")
async def cancel_downtime_prompt_handler(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return
    
    await state.clear()
    
    current_status, _ = await is_payments_enabled(session)
    text = await build_admin_menu_text(session, current_status)

    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(current_status), parse_mode="HTML")


@admin_router.message(StateFilter(AdminStates.waiting_for_downtime_range))
async def process_custom_downtime(message: Message, state: FSMContext, session: AsyncSession):
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    tz = ZoneInfo(settings.TIMEZONE)

    # Expected format: DD.MM HH:MM - DD.MM HH:MM
    try:
        parts = message.text.split("-")
        if len(parts) != 2:
            raise ValueError
        
        start_str = parts[0].strip()
        end_str = parts[1].strip()
        
        current_year = datetime.now(tz).year
        
        # Parse into naive objects first
        start_time_naive = datetime.strptime(f"{start_str}.{current_year}", "%d.%m %H:%M.%Y")
        end_time_naive = datetime.strptime(f"{end_str}.{current_year}", "%d.%m %H:%M.%Y")
        
        if end_time_naive <= start_time_naive:
            # If end time is technically before start time, it likely crossed into the next year
            end_time_naive = end_time_naive.replace(year=current_year + 1)
            
        # The admin enters time in local timezone. We attach local TZ to it.
        # Then we convert it to UTC before saving to DB, as SQLAlchemy DateTime is typically UTC.
        start_time_local = start_time_naive.replace(tzinfo=tz)
        end_time_local = end_time_naive.replace(tzinfo=tz)
        
        start_time_utc = start_time_local.astimezone(ZoneInfo("UTC"))
        end_time_utc = end_time_local.astimezone(ZoneInfo("UTC"))
            
    except ValueError:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=BUTTONS['admin_back_to_main'], callback_data="admin_cancel_downtime_prompt")]]
        )
        await message.answer(MESSAGES['admin_invalid_format_error'], reply_markup=kb, parse_mode="HTML")
        return

    db_settings = await get_global_settings(session)
    db_settings.scheduled_disable_at = start_time_utc
    db_settings.scheduled_enable_at = end_time_utc
    db_settings.use_custom_schedule = True
    db_settings.auto_enable_at = None
    
    await session.commit()
    
    start_fmt = start_time_local.strftime("%Y-%m-%d %H:%M")
    end_fmt = end_time_local.strftime("%Y-%m-%d %H:%M")
    
    # We don't render the whole menu here, just the confirmation message with a back button.
    # The back button will trigger admin_main_menu, which re-evaluates the state.
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="admin_main_menu")]]
    )
    await message.answer(MESSAGES['admin_range_saved'].format(start=start_fmt, end=end_fmt, tz=settings.TIMEZONE), reply_markup=kb, parse_mode="HTML")
    await state.clear()

@admin_router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return
    
    current_status, _ = await is_payments_enabled(session)
    text = await build_admin_menu_text(session, current_status)

    try:
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard(current_status), parse_mode="HTML")
    except Exception:
        # Ignore "message is not modified" exceptions if they happen
        pass

@admin_router.callback_query(F.data == "admin_close")
async def admin_close_handler(callback: CallbackQuery):
    await callback.message.delete()
