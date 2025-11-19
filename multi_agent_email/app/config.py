import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from a .env file into the system environment
load_dotenv()


@dataclass(frozen=True) # Making the dataclass immutable is good practice for config
class Settings:
    """
    Application-wide settings loaded from environment variables.

    Environment variables are cast to their appropriate types here.
    """
    # Vector Database Settings
    vector_db_dir: str = os.getenv("VECTOR_DB_DIR", ".chroma")

    # External Tool (News API) Settings
    tavily_api_key: Optional[str] = os.getenv("TAVILY_API_KEY")

    # --- Langfuse Configuration (Mandatory for monitoring) ---
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    # Use LANGFUSE_HOST only if you are using a self-hosted instance, otherwise
    # the default (cloud.langfuse.com) is used.
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Email (SMTP) Configuration
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    # Cast port to int, using a default string that can be safely cast
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: Optional[str] = os.getenv("SMTP_USER")
    smtp_pass: Optional[str] = os.getenv("SMTP_PASS")

    # Application Logic and Logging
    app_secret: str = os.getenv("APP_SECRET", "change-me")
    # Cast threshold to float
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
    log_file: str = os.getenv("LOG_FILE", "logs.jsonl")


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of the Settings object.
    """
    return Settings()