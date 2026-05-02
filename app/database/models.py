import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Text, DateTime, ForeignKey, func, Boolean, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

logger = logging.getLogger(__name__)

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
    
    scheduled_disable_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_enable_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    use_custom_schedule: Mapped[bool] = mapped_column(Boolean, default=False)

async def _check_and_migrate_columns(conn) -> None:
    # A simple schema migration check for SQLite.
    # Note: If your schema changes frequently, it's highly recommended to use Alembic.
    
    # 1. Check `users` table for `disclaimer_accepted`
    try:
        user_info = await conn.execute(text("PRAGMA table_info('users');"))
        user_columns = [row[1] for row in user_info.fetchall()]
        
        if "disclaimer_accepted" not in user_columns:
            logger.info("Migrating 'users' table: adding 'disclaimer_accepted' column")
            await conn.execute(text("ALTER TABLE users ADD COLUMN disclaimer_accepted BOOLEAN DEFAULT 0;"))
    except Exception as e:
        logger.error(f"Error migrating 'users' table: {e}")

    # 2. Check `global_settings` table for new downtime fields
    try:
        gs_info = await conn.execute(text("PRAGMA table_info('global_settings');"))
        gs_columns = [row[1] for row in gs_info.fetchall()]
        
        # In PRAGMA table_info result, row[1] is the column name.
        if "scheduled_disable_at" not in gs_columns:
            logger.info("Migrating 'global_settings': adding 'scheduled_disable_at'")
            await conn.execute(text("ALTER TABLE global_settings ADD COLUMN scheduled_disable_at DATETIME;"))
            
        if "scheduled_enable_at" not in gs_columns:
            logger.info("Migrating 'global_settings': adding 'scheduled_enable_at'")
            await conn.execute(text("ALTER TABLE global_settings ADD COLUMN scheduled_enable_at DATETIME;"))
            
        if "use_custom_schedule" not in gs_columns:
            logger.info("Migrating 'global_settings': adding 'use_custom_schedule'")
            await conn.execute(text("ALTER TABLE global_settings ADD COLUMN use_custom_schedule BOOLEAN DEFAULT 0;"))
            
    except Exception as e:
        logger.error(f"Error migrating 'global_settings' table: {e}")


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        # First, ensure all tables exist (this creates them if the DB is completely empty)
        await conn.run_sync(Base.metadata.create_all)
        
        # Then, check and apply any necessary manual migrations for existing tables
        await _check_and_migrate_columns(conn)
