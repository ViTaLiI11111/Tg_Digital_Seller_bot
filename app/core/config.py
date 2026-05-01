import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# Ensure the data directory exists
DATA_DIR = BASE_DIR / "data"
os.makedirs(DATA_DIR, exist_ok=True)

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int]
    # Default points to the data directory mapped in docker-compose.yml
    DB_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/bot_database.db"
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    PRIVATE_CHANNEL_ID: str = "-1003717175062"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
