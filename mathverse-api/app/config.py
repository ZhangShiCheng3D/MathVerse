"""Application settings from environment variables."""
from pydantic_settings import BaseSettings

DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    environment: str = "development"
    cors_origins: str = "*"  # comma-separated; "*" disables credentials
    database_url: str = "sqlite:///data/mathverse.db"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_days: int = 7
    deeptutor_url: str = "http://deeptutor:8001"
    # Admission control toward DeepTutor: cap concurrent in-flight calls so a
    # surge sheds onto the DeepSeek degrade path instead of overloading the engine.
    deeptutor_max_concurrency: int = 64
    deeptutor_admission_timeout: float = 8.0
    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    # DashScope (Alibaba) — multimodal vision for photo-solving (qwen-vl).
    dashscope_api_key: str = ""
    vision_model: str = "qwen-vl-max"
    math_ocr_api_key: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_pay_mch_id: str = ""
    wechat_pay_api_key: str = ""
    free_daily_quota: int = 10
    sensitive_words: str = ""  # comma-separated; operationally configured per deploy
    class Config:
        env_file = ".env"

settings = Settings()
