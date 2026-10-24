from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Every value comes from the root .env (see .env.example); none is defaulted in code,
    so a missing key stops the app at startup with the key's name."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = Field(default=...)
    DB_ECHO: bool = Field(default=...)
    DB_POOL_SIZE: int = Field(default=...)
    DB_MAX_OVERFLOW: int = Field(default=...)

    # LLM: any OpenAI-compatible chat completions endpoint.
    LLM_BASE_URL: str = Field(default=...)
    LLM_API_KEY: str = Field(default=...)
    LLM_MODEL: str = Field(default=...)
    LLM_TIMEOUT_SECONDS: float = Field(default=...)
    LLM_MAX_TOKENS: int = Field(default=...)
    # On HTTP 429 the call is retried once after Retry-After seconds (capped), or the default wait.
    LLM_RATE_LIMIT_DEFAULT_WAIT_SECONDS: float = Field(default=...)
    LLM_RATE_LIMIT_MAX_WAIT_SECONDS: float = Field(default=...)

    # Speech-to-text: any OpenAI-compatible transcription endpoint (whisper.cpp server locally).
    STT_BASE_URL: str = Field(default=...)
    STT_INFERENCE_PATH: str = Field(default=...)
    STT_API_KEY: str = Field(default=...)
    STT_MODEL: str = Field(default=...)
    STT_TIMEOUT_SECONDS: float = Field(default=...)
    STT_MAX_UPLOAD_MB: int = Field(default=...)

    # Below this, a complete entry is still confirmed with the trader before saving (FR-S5).
    CONFIDENCE_THRESHOLD: float = Field(default=...)
    # Model match of a new name to an existing customer (FR-S9): at or above LINK it is linked and
    # saved as an alias; at or above CONFIRM the trader is asked "Do you mean ...?"; below, a new customer.
    CUSTOMER_MATCH_LINK_CONFIDENCE: float = Field(default=...)
    CUSTOMER_MATCH_CONFIRM_CONFIDENCE: float = Field(default=...)
    # The same for an item name the model matches to the trader's inventory (FR-S25).
    ITEM_MATCH_LINK_CONFIDENCE: float = Field(default=...)
    ITEM_MATCH_CONFIRM_CONFIDENCE: float = Field(default=...)

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

    # Demo and access control.
    DEMO_MODE: bool = Field(default=...)  # no provider calls, rule-based interpretation (NFR-4)
    DEMO_CONTROLS_ENABLED: bool = Field(default=...)  # enables POST /demo/reset and /demo/seed (FR-C10)
    SESSION_TOKEN_TTL_DAYS: int = Field(default=...)  # trader session lifetime (BR-O4)
    AUTH_MAX_FAILED_LOGINS: int = Field(default=...)  # wrong PINs in a row before a lock (BR-O3)
    AUTH_LOCK_MINUTES: int = Field(default=...)  # how long the lock lasts
    ACCESS_TOKEN_TTL_MINUTES: int = Field(default=...)  # lender agent token lifetime (FR-S14)
    CORS_ORIGINS: list[str] = Field(default=...)  # allowed browser origins, a JSON list (NFR-7)


settings = Settings()
