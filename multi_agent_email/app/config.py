import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    vector_db_dir: str = os.getenv("VECTOR_DB_DIR", ".chroma")

    news_api_url: str | None = os.getenv("NEWS_API_URL")
    news_api_key: str | None = os.getenv("NEWS_API_KEY")

    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str | None = os.getenv("SMTP_USER")
    smtp_pass: str | None = os.getenv("SMTP_PASS")

    app_secret: str = os.getenv("APP_SECRET", "change-me")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
    log_file: str = os.getenv("LOG_FILE", "logs.jsonl")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
