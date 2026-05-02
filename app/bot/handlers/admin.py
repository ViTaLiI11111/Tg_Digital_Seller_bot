from datetime import datetime, timedelta
from typing import Optional

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

def get_admin_keyboard(payments_enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "🟢 Платежи включены" if payments_enabled else "🔴 Платежи выключены"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔄 {toggle_text}", callback_data="admin_toggle_payments")],
            [InlineKeyboardButton(text=BUTTONS['admin_enable_shabbat'], callback_data="admin_shabbat_menu")],
            [InlineKeyboardButton(text=BUTTONS['admin_custom_downtime'], callback_data="admin_custom_downtime_prompt")],
            [InlineKeyboardButton(text=BUTTONS['admin_close'], callback_data="admin_close")]
        ]
    )

@admin_router.message(Command("secret_admin"))
async def secret_admin_command(message: Message, state: FSMContext):
    await message.answer(MESSAGES['admin_prompt_password'])
    await state.set_state(AdminStates.waiting_for_password)

@admin_router.message(StateFilter(AdminStates.waiting_for_password))
async def process_admin_password(message: Message, state: FSMContext, session: AsyncSession):
    if message.from_user.id in settings.ADMIN_IDS:
        db_settings = await get_global_settings(session)
        
        status_text = "Включены" if db_settings.payments_enabled else "Выключены"
        text = f"{MESSAGES['admin_welcome']}\n\n{MESSAGES['admin_payments_status'].format(status=status_text)}"
        
        if db_settings.auto_enable_at and not db_settings.use_custom_schedule:
            time_str = db_settings.auto_enable_at.strftime("%Y-%m-%d %H:%M:%S")
            text += f"\n⏳ Авто-включение (Шаббат): <b>{time_str}</b>"
        elif db_settings.use_custom_schedule and db_settings.scheduled_disable_at and db_settings.scheduled_enable_at:
            start_str = db_settings.scheduled_disable_at.strftime("%Y-%m-%d %H:%M")
            end_str = db_settings.scheduled_enable_at.strftime("%Y-%m-%d %H:%M")
            text += f"\n⏳ Свой период отключения:\nС: <b>{start_str}</b>\nПо: <b>{end_str}</b>"

        await message.answer(text, reply_markup=get_admin_keyboard(db_settings.payments_enabled), parse_mode="HTML")
        await state.clear()
    else:
        await message.answer(MESSAGES['admin_wrong_password'])
        await state.clear()

@admin_router.callback_query(F.data == "admin_toggle_payments")
async def toggle_payments_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    db_settings = await get_global_settings(session)
    db_settings.payments_enabled = not db_settings.payments_enabled
    db_settings.auto_enable_at = None 
    db_settings.use_custom_schedule = False
    await session.commit()
    
    status_text = "Включены" if db_settings.payments_enabled else "Выключены"
    text = f"{MESSAGES['admin_welcome']}\n\n{MESSAGES['admin_payments_status'].format(status=status_text)}"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_admin_keyboard(db_settings.payments_enabled),
        parse_mode="HTML"
    )
    await callback.answer("Статус платежей изменен")

@admin_router.callback_query(F.data == "admin_shabbat_menu")
async def shabbat_menu_handler(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS['shabbat_time_1'], callback_data="set_shabbat_sat_20")],
            [InlineKeyboardButton(text=BUTTONS['shabbat_time_2'], callback_data="set_shabbat_sun_09")],
            [InlineKeyboardButton(text=BUTTONS['shabbat_cancel'], callback_data="admin_main_menu")]
        ]
    )
    await callback.message.edit_text("Выберите время автоматического включения платежей после Шаббата:", reply_markup=kb)

@admin_router.callback_query(F.data.startswith("set_shabbat_"))
async def set_shabbat_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

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
    db_settings.auto_enable_at = enable_time
    db_settings.use_custom_schedule = False
    await session.commit()

    time_str = enable_time.strftime("%Y-%m-%d %H:%M:%S")
    await callback.message.edit_text(
        MESSAGES['admin_shabbat_enabled'].format(time=time_str),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="admin_main_menu")]]
        )
    )

@admin_router.callback_query(F.data == "admin_custom_downtime_prompt")
async def custom_downtime_prompt_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return
    
    await callback.message.edit_text(MESSAGES['admin_custom_range_prompt'], parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_downtime_range)

@admin_router.message(StateFilter(AdminStates.waiting_for_downtime_range))
async def process_custom_downtime(message: Message, state: FSMContext, session: AsyncSession):
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    # Expected format: DD.MM HH:MM - DD.MM HH:MM
    try:
        parts = message.text.split("-")
        if len(parts) != 2:
            raise ValueError
        
        start_str = parts[0].strip()
        end_str = parts[1].strip()
        
        current_year = datetime.utcnow().year
        
        start_time = datetime.strptime(f"{start_str}.{current_year}", "%d.%m %H:%M.%Y")
        end_time = datetime.strptime(f"{end_str}.{current_year}", "%d.%m %H:%M.%Y")
        
        if end_time <= start_time:
            # If end time is technically before start time, it likely crossed into the next year
            end_time = end_time.replace(year=current_year + 1)
            
    except ValueError:
        await message.answer(MESSAGES['admin_invalid_format_error'], parse_mode="HTML")
        return

    db_settings = await get_global_settings(session)
    db_settings.scheduled_disable_at = start_time
    db_settings.scheduled_enable_at = end_time
    db_settings.use_custom_schedule = True
    db_settings.auto_enable_at = None
    
    # We do NOT set payments_enabled = False immediately here, unless current time is already within the range.
    # The check is handled dynamically in user.py
    
    await session.commit()
    
    start_fmt = start_time.strftime("%Y-%m-%d %H:%M")
    end_fmt = end_time.strftime("%Y-%m-%d %H:%M")
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В главное меню", callback_data="admin_main_menu")]]
    )
    await message.answer(MESSAGES['admin_range_saved'].format(start=start_fmt, end=end_fmt), reply_markup=kb, parse_mode="HTML")
    await state.clear()

@admin_router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu_handler(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return
    
    db_settings = await get_global_settings(session)
    status_text = "Включены" if db_settings.payments_enabled else "Выключены"
    text = f"{MESSAGES['admin_welcome']}\n\n{MESSAGES['admin_payments_status'].format(status=status_text)}"
    
    if db_settings.auto_enable_at and not db_settings.use_custom_schedule:
        time_str = db_settings.auto_enable_at.strftime("%Y-%m-%d %H:%M:%S")
        text += f"\n⏳ Авто-включение (Шаббат): <b>{time_str}</b>"
    elif db_settings.use_custom_schedule and db_settings.scheduled_disable_at and db_settings.scheduled_enable_at:
        start_str = db_settings.scheduled_disable_at.strftime("%Y-%m-%d %H:%M")
        end_str = db_settings.scheduled_enable_at.strftime("%Y-%m-%d %H:%M")
        text += f"\n⏳ Свой период отключения:\nС: <b>{start_str}</b>\nПо: <b>{end_str}</b>"

    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(db_settings.payments_enabled), parse_mode="HTML")

@admin_router.callback_query(F.data == "admin_close")
async def admin_close_handler(callback: CallbackQuery):
    await callback.message.delete()
