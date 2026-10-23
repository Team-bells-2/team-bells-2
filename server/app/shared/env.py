from pathlib import Path

from pydantic import Field
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

    # LLM: any OpenAI-compatible chat completions endpoint.
    LLM_BASE_URL: str = Field(default=...)
    LLM_API_KEY: str = Field(default=...)
    LLM_MODEL: str = Field(default=...)
    LLM_TIMEOUT_SECONDS: float = Field(default=...)
    LLM_MAX_TOKENS: int = Field(default=...)

    # Speech-to-text: any OpenAI-compatible transcription endpoint (whisper.cpp server locally).
    STT_BASE_URL: str = Field(default=...)
    STT_INFERENCE_PATH: str = Field(default=...)
    STT_API_KEY: str = Field(default=...)
    STT_MODEL: str = Field(default=...)
    STT_TIMEOUT_SECONDS: float = Field(default=...)
    STT_MAX_UPLOAD_MB: int = Field(default=...)

    # Below this, a complete entry is still confirmed with the trader before saving (FR-S5).
    CONFIDENCE_THRESHOLD: float = Field(default=...)

    # Restock ranking (FR-S30): the five factor weights and the distance at which the distance score halves.
    SUGGESTION_WEIGHT_DISTANCE: float = Field(default=...)
    SUGGESTION_WEIGHT_RATING: float = Field(default=...)
    SUGGESTION_WEIGHT_QUALITY: float = Field(default=...)
    SUGGESTION_WEIGHT_COST: float = Field(default=...)
    SUGGESTION_WEIGHT_QUANTITY: float = Field(default=...)
    SUGGESTION_DISTANCE_HALF_KM: float = Field(default=...)
    # Score (0 to 1) for each supplier quality grade.
    SUGGESTION_QUALITY_SCORE_A: float = Field(default=...)
    SUGGESTION_QUALITY_SCORE_B: float = Field(default=...)
    SUGGESTION_QUALITY_SCORE_C: float = Field(default=...)


settings = Settings()
