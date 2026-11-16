from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Durga Boutique and Dry Cleaning"
    database_url: str = "postgresql+psycopg://durga_app:local-development-only@localhost:5432/durga_business"
    session_secret: str = "development-only-change-before-use"
    business_timezone: str = "Asia/Kolkata"
    media_root: str = "./data/media"
    shop_whatsapp_number: str = ""
    app_origin: str = "http://localhost:3000"
    session_cookie_secure: bool = False
    session_ttl_days: int = 30
    auto_create_schema: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
