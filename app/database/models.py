from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Text, DateTime, ForeignKey, func, Boolean
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    disclaimer_accepted: Mapped[bool] = mapped_column(Boolean, default=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"))
    product_id: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="pending")

    user: Mapped["User"] = relationship(back_populates="orders")

class TextContent(Base):
    __tablename__ = "text_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    content: Mapped[str] = mapped_column(Text)

class GlobalSettings(Base):
    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    payments_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_enable_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
