# backend/config.py
from typing import List, Any

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

        DATABASE_URL: str = "sqlite+aiosqlite:///./researchform_dev.db"
        SYNC_DATABASE_URL: str = "sqlite:///./researchform_dev.db"
        SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
        ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
        ANTHROPIC_API_KEY: str = ""
        OPENROUTER_API_KEY: str = ""
        OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
        REDIS_URL: str = ""
        CELERY_BROKER_URL: str = ""
        CELERY_RESULT_BACKEND: str = ""
        STORAGE_DIR: str = "storage"
        CHARTS_DIR: str = "storage/charts"
        REPORTS_DIR: str = "storage/reports"
        DATANEST_API_URL: str = "http://localhost:8001/api/market"
        ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"]
        APP_NAME: str = "ResearchForm"
        DEBUG: bool = True
        DEV_MODE: bool = True
        
        # S3 / MinIO
        S3_ENDPOINT_URL: str = ""
        S3_ACCESS_KEY: str = ""
        S3_SECRET_KEY: str = ""
        S3_REGION: str = "us-east-1"
        S3_BUCKET_DATASETS: str = "datanest-datasets"
        S3_BUCKET_THUMBNAILS: str = "datanest-thumbnails"
        S3_BUCKET_SAMPLES: str = "datanest-samples"
        S3_BUCKET_ID_DOCS: str = "datanest-id-docs"
        
        # Marketplace
        MAX_FILE_SIZE_MB: int = 50
        MIN_WITHDRAWAL_NAIRA: float = 5000.0
        CREDIT_PER_1K_INPUT_TOKENS: float = 0.35
        CREDIT_PER_1K_OUTPUT_TOKENS: float = 1.75
        CREDIT_MARKUP_MULTIPLIER: float = 1.40
        CREDIT_MIN_REPORT_CHARGE: float = 2.0
        SIGNUP_BONUS_CREDITS: float = 5.0
        EARNINGS_HOLD_DAYS: int = 2
        CREDIT_PACKAGES: List[Any] = [
            {"id": "starter", "label": "Starter", "credits": 25, "price_naira": 1500, "description": "~5–8 reports"},
            {"id": "standard", "label": "Standard", "credits": 75, "price_naira": 4000, "description": "~15–25 reports"},
            {"id": "pro", "label": "Pro", "credits": 200, "price_naira": 10000, "description": "~40+ reports"},
            {"id": "lab", "label": "Lab Pack", "credits": 500, "price_naira": 22000, "description": "Departments & labs"},
        ]
        PAYSTACK_SECRET_KEY: str = ""
        PAYSTACK_PUBLIC_KEY: str = ""
        STRIPE_SECRET_KEY: str = ""
        STRIPE_PUBLIC_KEY: str = ""
        FRONTEND_URL: str = "http://localhost:3000"
        GOOGLE_CLIENT_ID: str = ""
        GOOGLE_CLIENT_SECRET: str = ""
        FACEBOOK_CLIENT_ID: str = ""
        FACEBOOK_CLIENT_SECRET: str = ""
        # Localization
        CURRENCY: str = "NGN"                   # change to USD/GBP/EUR for intl deployments
        CURRENCY_SYMBOL: str = "₦"              # displayed in frontend
        CURRENCY_LOCALE: str = "en-NG"          # BCP 47 locale for number formatting
        # Performance
        HEALTH_CACHE_TTL_SECONDS: int = 300     # 5-min TTL for reliability/VIF/normality results

except ImportError:
    from pydantic import BaseSettings  # type: ignore

    class Settings(BaseSettings):  # type: ignore
        DATABASE_URL: str = "sqlite+aiosqlite:///./researchform_dev.db"
        SYNC_DATABASE_URL: str = "sqlite:///./researchform_dev.db"
        SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
        ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
        ANTHROPIC_API_KEY: str = ""
        OPENROUTER_API_KEY: str = ""
        OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
        REDIS_URL: str = ""
        CELERY_BROKER_URL: str = ""
        CELERY_RESULT_BACKEND: str = ""
        STORAGE_DIR: str = "storage"
        CHARTS_DIR: str = "storage/charts"
        REPORTS_DIR: str = "storage/reports"
        DATANEST_API_URL: str = "http://localhost:8001/api/market"
        ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"]
        APP_NAME: str = "ResearchForm"
        DEBUG: bool = True
        DEV_MODE: bool = True
        
        # S3 / MinIO
        S3_ENDPOINT_URL: str = ""
        S3_ACCESS_KEY: str = ""
        S3_SECRET_KEY: str = ""
        S3_REGION: str = "us-east-1"
        S3_BUCKET_DATASETS: str = "datanest-datasets"
        S3_BUCKET_THUMBNAILS: str = "datanest-thumbnails"
        S3_BUCKET_SAMPLES: str = "datanest-samples"
        S3_BUCKET_ID_DOCS: str = "datanest-id-docs"
        
        # Marketplace
        MAX_FILE_SIZE_MB: int = 50
        MIN_WITHDRAWAL_NAIRA: float = 5000.0
        CREDIT_PER_1K_INPUT_TOKENS: float = 0.35
        CREDIT_PER_1K_OUTPUT_TOKENS: float = 1.75
        CREDIT_MARKUP_MULTIPLIER: float = 1.40
        CREDIT_MIN_REPORT_CHARGE: float = 2.0
        SIGNUP_BONUS_CREDITS: float = 5.0
        EARNINGS_HOLD_DAYS: int = 2
        CREDIT_PACKAGES: List[Any] = [
            {"id": "starter", "label": "Starter", "credits": 25, "price_naira": 1500, "description": "~5–8 reports"},
            {"id": "standard", "label": "Standard", "credits": 75, "price_naira": 4000, "description": "~15–25 reports"},
            {"id": "pro", "label": "Pro", "credits": 200, "price_naira": 10000, "description": "~40+ reports"},
            {"id": "lab", "label": "Lab Pack", "credits": 500, "price_naira": 22000, "description": "Departments & labs"},
        ]
        PAYSTACK_SECRET_KEY: str = ""
        PAYSTACK_PUBLIC_KEY: str = ""
        STRIPE_SECRET_KEY: str = ""
        STRIPE_PUBLIC_KEY: str = ""
        FRONTEND_URL: str = "http://localhost:3000"
        GOOGLE_CLIENT_ID: str = ""
        GOOGLE_CLIENT_SECRET: str = ""
        FACEBOOK_CLIENT_ID: str = ""
        FACEBOOK_CLIENT_SECRET: str = ""
        # Localization
        CURRENCY: str = "NGN"
        CURRENCY_SYMBOL: str = "₦"
        CURRENCY_LOCALE: str = "en-NG"
        # Performance
        HEALTH_CACHE_TTL_SECONDS: int = 300

        class Config:
            env_file = ".env"
            extra = "ignore"

settings = Settings()
