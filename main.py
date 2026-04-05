import asyncio
from contextlib import asynccontextmanager
from typing import Callable, Dict, Any, Awaitable

import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject

from app.core.config import settings
from app.api.webhooks import webhook_router
from app.bot.handlers.user import user_router
from app.database.models import init_db
from app.database.session import engine, async_session_maker

class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(engine)

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(user_router)

    app.state.bot = bot

    polling_task = asyncio.create_task(dp.start_polling(bot))

    yield

    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    finally:
        await bot.session.close()

app = FastAPI(lifespan=lifespan)
app.include_router(webhook_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
