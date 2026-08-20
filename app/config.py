from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    NODE_ENV: Literal["development", "production", "test"] = "development"
    PORT: int = Field(default=3001, gt=0)
    FRONTEND_URL: str = "http://localhost:3000"
    DATABASE_URL: str | None = None
    DIRECT_URL: str | None = None
    CLERK_SECRET_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    MT5_CONNECTION_TOKEN_SECRET: str | None = None
    BLOB_READ_WRITE_TOKEN: str | None = None

    @field_validator("FRONTEND_URL")
    @classmethod
    def validate_frontend_url(cls, value: str) -> str:
        for part in value.split(","):
            url = part.strip()
            if not url:
                continue
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(
                    "FRONTEND_URL must be one or more valid URLs separated by commas"
                )
        return value

    @property
    def is_production(self) -> bool:
        return self.NODE_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
