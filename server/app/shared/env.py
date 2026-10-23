from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    DATABASE_URL: str = Field(default=...)
    DB_ECHO: bool = Field(default=...)
    DB_POOL_SIZE: int = Field(default=...)
    DB_MAX_OVERFLOW: int = Field(default=...)


settings = Settings()
