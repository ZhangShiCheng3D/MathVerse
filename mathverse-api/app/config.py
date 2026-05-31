"""Application settings from environment variables."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///data/mathverse.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_days: int = 7
    deeptutor_url: str = "http://deeptutor:8001"
    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    math_ocr_api_key: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_pay_mch_id: str = ""
    wechat_pay_api_key: str = ""
    free_daily_quota: int = 10
    class Config:
        env_file = ".env"

settings = Settings()
