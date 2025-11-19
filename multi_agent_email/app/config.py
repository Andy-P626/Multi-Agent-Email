import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pathlib import Path

# Try to load the repository-root .env file explicitly (more robust than
# relying on the current working directory). Fall back to load_dotenv()
# which will search parent directories if needed.
repo_root = Path(__file__).resolve().parents[2]
env_path = repo_root / ".env"
if env_path.exists():
    load_dotenv(str(env_path))
else:
    load_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return an environment variable stripped of whitespace and internal newlines.

    This helps when .env files have wrapped lines or stray CR/LF inside quoted
    values; we normalize them so downstream code receives clean strings.
    """
    v = os.getenv(name, default)
    if v is None:
        return None
    if isinstance(v, str):
        # remove carriage-returns/newlines that sometimes appear in copied keys
        v = v.replace("\r", "").replace("\n", "")
        v = v.strip()
    return v


@dataclass(frozen=True) # Making the dataclass immutable is good practice for config
class Settings:
    """
    Application-wide settings loaded from environment variables.

    Environment variables are cast to their appropriate types here.
    """
    # Vector Database Settings
    vector_db_dir: str = _env("VECTOR_DB_DIR") or ".chroma"

    # External Tool (News API) Settings
    tavily_api_key: Optional[str] = _env("TAVILY_API_KEY")

    # --- Langfuse Configuration (Mandatory for monitoring) ---
    langfuse_public_key: str = _env("LANGFUSE_PUBLIC_KEY") or ""
    langfuse_secret_key: str = _env("LANGFUSE_SECRET_KEY") or ""
    # Use LANGFUSE_HOST only if you are using a self-hosted instance, otherwise
    # the default (cloud.langfuse.com) is used.
    langfuse_host: str = _env("LANGFUSE_HOST") or "https://cloud.langfuse.com"

    # Email (SMTP) Configuration
    smtp_host: str = _env("SMTP_HOST") or "smtp.gmail.com"
    # Cast port to int, using a default string that can be safely cast
    try:
        smtp_port: int = int((_env("SMTP_PORT") or "587"))
    except ValueError:
        smtp_port: int = 587
    smtp_user: Optional[str] = _env("SMTP_USER")
    smtp_pass: Optional[str] = _env("SMTP_PASS")

    # Application Logic and Logging
    app_secret: str = _env("APP_SECRET") or "change-me"
    # Cast threshold to float
    try:
        confidence_threshold: float = float((_env("CONFIDENCE_THRESHOLD") or "0.65"))
    except ValueError:
        confidence_threshold: float = 0.65
    log_file: str = _env("LOG_FILE") or "logs.jsonl"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of the Settings object.
    """
    return Settings()