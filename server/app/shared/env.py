from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    DATABASE_URL: str
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OJA_MODEL: str = "gpt-5-nano"
    OJA_STT_MODEL: str = "whisper-1"
    LLM_TIMEOUT_SECONDS: float = 15.0
    # True skips every provider call and uses the rule-based extractor (offline demo, NFR-4).
    DEMO_MODE: bool = False
    # Enables POST /demo/reset and /demo/seed. Never enable on a shared deployment.
    DEMO_CONTROLS_ENABLED: bool = False
    SESSION_TOKEN_TTL_DAYS: int = 30
    ACCESS_TOKEN_TTL_MINUTES: int = 43200
    CORS_ORIGINS: list[str] = []


settings = Settings()
