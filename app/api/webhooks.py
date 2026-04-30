import logging
import stripe
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database.models import Order
from app.database.session import get_db_session
from app.core.config import settings
from app.bot.lexicon import MESSAGES, BUTTONS

logger = logging.getLogger(__name__)

webhook_router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

@webhook_router.post("/stripe-webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    session: AsyncSession = Depends(get_db_session)
):
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session_obj = event['data']['object']
        order_id_str = session_obj.get('metadata', {}).get('order_id')
        
        if not order_id_str:
            return {"status": "ok"}
            
        try:
            order_id = int(order_id_str)
        except ValueError:
            return {"status": "ok"}
            
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()

        if order and order.status == 'pending':
            order.status = 'success'
            await session.commit()

            bot = request.app.state.bot

            if order.product_id == 1:
                pdf_file_id = "BQACAgIAAxkBAAMFafO7pK-zRG1iiUGrwcZ4CFPLHVMAAiabAAL8HaFLZZxmg_jJGSQ7BA"

                # Закоментовано миттєвий апсел
                # kb_next = InlineKeyboardMarkup(
                #     inline_keyboard=[
                #         [InlineKeyboardButton(text=BUTTONS['continue_14_days'], callback_data="buy_39")]
                #     ]
                # )

                await bot.send_document(
                    chat_id=order.user_id,
                    document=pdf_file_id,
                    caption=MESSAGES['access_opened_1']
                )

                # await bot.send_message(
                #     chat_id=order.user_id,
                #     text=MESSAGES['upsell_after_1'],
                #     reply_markup=kb_next
                # )

            elif order.product_id == 2:
                channel_id = "-1003717175062"

                try:
                    invite_link = await bot.create_chat_invite_link(
                        chat_id=channel_id,
                        member_limit=1,
                        name=f"Оплата 39€ (User {order.user_id})"
                    )

                    # Закоментовано апсел 89 євро
                    # kb_pro = InlineKeyboardMarkup(
                    #     inline_keyboard=[
                    #         [InlineKeyboardButton(text=BUTTONS['want_pro'], callback_data="buy_89")]
                    #     ]
                    # )

                    await bot.send_message(
                        chat_id=order.user_id,
                        text=MESSAGES['access_opened_2'].format(invite_link=invite_link.invite_link),
                        # reply_markup=kb_pro
                    )
                except Exception as e:
                    logger.error(f"Помилка створення посилання (Бот не адмін?): {e}")
                    await bot.send_message(
                        order.user_id,
                        MESSAGES['link_generation_error']
                    )

            # Закоментовано логіку видачі 89 євро
            # elif order.product_id == 3:
            #     await bot.send_message(
            #         chat_id=order.user_id,
            #         text=MESSAGES['access_opened_3']
            #     )

    return {"status": "success"}
