import json
import re
import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database.models import Order
from app.database.session import get_db_session

logger = logging.getLogger(__name__)

webhook_router = APIRouter()

@webhook_router.post("/kofi-webhook")
async def kofi_webhook(request: Request, session: AsyncSession = Depends(get_db_session)):
    try:
        form = await request.form()
        data_str = form.get("data")
        
        if not data_str:
            return {"status": "ok"}
            
        data = json.loads(data_str)
        message = data.get("message", "")
        
        match = re.search(r"PAY-[A-Za-z0-9]+", message)
        if match:
            ko_fi_code = match.group(0)
            
            stmt = select(Order).where(Order.ko_fi_code == ko_fi_code)
            result = await session.execute(stmt)
            order = result.scalar_one_or_none()

            if order and order.status == 'pending':
                order.status = 'success'
                await session.commit()

                bot = request.app.state.bot

                if order.product_id == 1:
                    pdf_file_id = "BQACAgIAAxkBAAMDadAXDRZfeDNy9Sfm2beamaBndE4AAnuRAAIT4IFKU3STNwxlnlE7BA"

                    kb_next = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Продолжить → 14 дней", callback_data="buy_39")]
                        ]
                    )

                    await bot.send_document(
                        chat_id=order.user_id,
                        document=pdf_file_id,
                        caption="Доступ открыт. Начните с первого дня. 👆"
                    )

                    await bot.send_message(
                        chat_id=order.user_id,
                        text="Хотите полную перезагрузку? Переходите на 14-дневную программу.",
                        reply_markup=kb_next
                    )

                elif order.product_id == 2:
                    channel_id = "-1003717175062"

                    try:
                        invite_link = await bot.create_chat_invite_link(
                            chat_id=channel_id,
                            member_limit=1,
                            name=f"Оплата 39€ (User {order.user_id})"
                        )

                        kb_pro = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="Хочу сопровождение (PRO)", callback_data="buy_89")]
                            ]
                        )

                        await bot.send_message(
                            chat_id=order.user_id,
                            text=f"Вы подключены к программе! 🎉\n\nВаше унікальне посилання на закритий канал (діє 1 раз):\n{invite_link.invite_link}",
                            reply_markup=kb_pro
                        )
                    except Exception as e:
                        logger.error(f"Помилка створення посилання (Бот не адмін?): {e}")
                        await bot.send_message(order.user_id,
                                               "Оплата пройшла, але виникла помилка з генерацією посилання. Зверніться до підтримки.")

                elif order.product_id == 3:
                    await bot.send_message(
                        chat_id=order.user_id,
                        text="Оплата PRO успішна! 🏆\n\nНапишите в личные сообщения @username_админа для подключения к сопровождению."
                    )

    except Exception as e:
        logger.error(f"Помилка при обробці Ko-fi вебхуку: {e}", exc_info=True)
        
    return {"status": "ok"}
