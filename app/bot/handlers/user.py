import uuid
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Document
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database.models import User, Order

user_router = Router()

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

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купити за 19€", callback_data="buy_19")]
        ]
    )
    await message.answer(
        "Привіт! Натисни кнопку нижче, щоб придбати доступ.",
        reply_markup=kb
    )

@user_router.callback_query(F.data == "buy_19")
async def process_buy_19(callback: CallbackQuery, session: AsyncSession):
    ko_fi_code = f"PAY-{uuid.uuid4().hex[:6].upper()}"
    
    order = Order(
        user_id=callback.from_user.id,
        product_id=1,
        ko_fi_code=ko_fi_code,
        status='pending'
    )
    session.add(order)
    await session.commit()

    await callback.message.answer(
        f"Супер! Для оплати перейдіть на Ko-fi.\n\n"
        f"При оплаті <b>ОБОВ'ЯЗКОВО</b> вкажіть цей код у повідомленні до донату:\n"
        f"<code>{ko_fi_code}</code>",
        parse_mode="HTML"
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
    ko_fi_code = f"PAY-{uuid.uuid4().hex[:6].upper()}"

    order = Order(
        user_id=callback.from_user.id,
        product_id=2,
        ko_fi_code=ko_fi_code,
        status='pending'
    )
    session.add(order)
    await session.commit()

    await callback.message.answer(
        f"🌟 <b>14 Lady Reset — полная перезагрузка ЖКТ (39€)</b>\n\n"
        f"Для оплати перейдіть на Ko-fi.\n"
        f"⚠️ ОБОВ'ЯЗКОВО вкажіть цей код у повідомленні до донату: <code>{ko_fi_code}</code>",
        parse_mode="HTML"
    )
    await callback.answer()

@user_router.callback_query(F.data == "buy_89")
async def process_buy_89(callback: CallbackQuery, session: AsyncSession):
    ko_fi_code = f"PAY-{uuid.uuid4().hex[:6].upper()}"

    order = Order(
        user_id=callback.from_user.id,
        product_id=3,
        ko_fi_code=ko_fi_code,
        status='pending'
    )
    session.add(order)
    await session.commit()

    await callback.message.answer(
        f"👑 <b>Lady Reset PRO — Сопровождение (89€)</b>\n\n"
        f"Для оплати перейдіть на Ko-fi.\n"
        f"⚠️ ОБОВ'ЯЗКОВО вкажіть цей код у повідомленні до донату: <code>{ko_fi_code}</code>",
        parse_mode="HTML"
    )
    await callback.answer()
