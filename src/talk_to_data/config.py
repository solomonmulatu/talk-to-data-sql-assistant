from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def normalize_database_url(url: str) -> str:
    """Adapt common Postgres URLs for SQLAlchemy + psycopg (incl. Supabase)."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    is_supabase = "supabase.co" in host or "supabase.com" in host
    if is_supabase and "sslmode" not in {key.lower() for key in query}:
        query["sslmode"] = "require"

    return urlunparse(parsed._replace(query=urlencode(query)))


class Settings(BaseSettings):
    openai_api_key: str
    openai_chat_model: str = "gpt-4o"

    api_base_url: str = "http://127.0.0.1:8000"
    database_url: str

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


settings = Settings()
