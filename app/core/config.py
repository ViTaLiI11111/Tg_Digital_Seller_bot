from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    BOT_TOKEN: str
    KOFI_WEBHOOK_SECRET: Optional[str] = None
    ADMIN_IDS: List[int]
    DB_URL: str = "sqlite+aiosqlite:///./bot_database.db"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
