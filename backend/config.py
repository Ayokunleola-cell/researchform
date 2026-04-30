# backend/config.py
from pydantic import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./researchform_dev.db"
    SYNC_DATABASE_URL: str = "sqlite:///./researchform_dev.db"
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ANTHROPIC_API_KEY: str = ""
    REDIS_URL: str = ""
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    STORAGE_DIR: str = "storage"
    CHARTS_DIR: str = "storage/charts"
    REPORTS_DIR: str = "storage/reports"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"]
    APP_NAME: str = "ResearchForm"
    DEBUG: bool = True
    DEV_MODE: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
