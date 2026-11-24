"""Environment-based configuration. No secrets live in source code.

All values come from environment variables (or a local, git-ignored `.env`).
See `.env.example` at the repo root for the list of names.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/ directory. The env file and relative paths are anchored here, so starting the
# API (or Alembic, or the worker) from any working directory gives the same configuration.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
TEST_CLUSTER_PORT = 54329  # backend/scripts/test_db.py


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Optional so the API can start (and report "not_ready") without a database.
    # SecretStr keeps the password out of reprs and logs.
    database_url: SecretStr | None = None
    database_connect_timeout: int = Field(default=5, ge=1, le=60)

    # Comma-separated in the environment, e.g. "http://localhost:5173,https://demo.example".
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # Private upload storage root (used from Phase 2). Never served directly.
    storage_path: Path = Path("./var/uploads")
    # Directory holding installed model versions (used from Phase 3).
    model_path: Path = Path("./var/models")
    # Optional deploy-time model fetch (scripts/fetch_model.py); both must be set to act.
    model_package_url: str | None = None
    model_package_sha256: str | None = None

    # Crop Doctor uploads (SECURITY.md: type, size, dimensions, decode checks).
    upload_max_bytes: int = Field(default=8 * 1024 * 1024, ge=64 * 1024, le=25 * 1024 * 1024)
    upload_max_images: int = Field(default=5, ge=1, le=10)  # per submission
    case_max_images: int = Field(default=20, ge=1, le=100)
    image_min_side: int = Field(default=128, ge=32)
    image_max_side: int = Field(default=8000, le=12000)
    image_max_pixels: int = Field(default=40_000_000, le=100_000_000)  # decompression bombs
    image_store_max_side: int = Field(default=2048, ge=512, le=4096)  # stored derivative
    image_thumb_side: int = Field(default=480, ge=160, le=800)
    storage_quota_bytes_per_user: int = Field(default=500 * 1024 * 1024, ge=1024 * 1024)
    case_create_limit_per_hour: int = Field(default=30, ge=1)
    register_limit_per_hour: int = Field(default=10, ge=1)  # per client IP
    signed_url_seconds: int = Field(default=600, ge=30, le=3600)
    # Run the job worker inside the API process (single-process dev/demo only).
    embedded_worker: bool = False

    # Weather provider (Open-Meteo needs no key). "disabled" -> honest unavailable state.
    weather_provider: Literal["open_meteo", "disabled"] = "open_meteo"
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_s: float = Field(default=8.0, ge=1, le=30)
    weather_cache_minutes: int = Field(default=30, ge=1, le=720)

    # Knowledge (RAG). Both providers default to "none": the system must work without an LLM
    # (hard rule 8) — answers are then extractive, quoted passages with citations.
    llm_provider: Literal["none", "groq", "xai", "ollama", "openai_compatible"] = "none"
    llm_base_url: str | None = None  # preset per provider; required for openai_compatible
    llm_model: str | None = None  # preset per provider
    llm_fallback_model: str | None = None  # tried on HTTP 429 (groq preset: gpt-oss-20b)
    llm_vision_model: str | None = None  # image-capable model (groq preset: qwen/qwen3.8-27b)
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY", "XAI_API_KEY")
    )
    llm_timeout_s: float = Field(default=40.0, ge=2, le=120)
    llm_max_tokens: int = Field(default=1200, ge=64, le=4000)
    embedding_provider: Literal["none", "fastembed"] = "none"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_cache_path: Path = Path("./var/models/embeddings")
    knowledge_upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    knowledge_ask_limit_per_minute: int = Field(default=20, ge=1)

    # Auth. JWT_SECRET is required outside development/test (checked below).
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    # Refresh cookie must be Secure on HTTPS deployments; off only for local http.
    cookie_secure: bool = False

    # Interactive API docs: on outside production; production needs an explicit opt-in.
    api_docs_enabled: bool | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _psycopg_driver(cls, value: object) -> object:
        # Hosted Postgres (e.g. Render) hands out postgres:// or postgresql:// URLs; SQLAlchemy
        # maps those to psycopg2, which is not installed. Pin the psycopg (v3) driver instead.
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str):
            for scheme in ("postgres://", "postgresql://"):
                if raw.startswith(scheme):
                    return "postgresql+psycopg://" + raw[len(scheme) :]
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _check_cors(self) -> "Settings":
        if "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must list explicit origins; '*' is not allowed")
        return self

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "Settings":
        secret = self.jwt_secret.get_secret_value() if self.jwt_secret else ""
        if self.app_env == "production" and len(secret) < 32:
            raise ValueError("JWT_SECRET must be set (>= 32 characters) in production")
        if secret and len(secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return self

    @field_validator("storage_path", "model_path", "embedding_cache_path", mode="after")
    @classmethod
    def _anchor_relative(cls, v: Path) -> Path:
        return v if v.is_absolute() else (BACKEND_DIR / v).resolve()

    @property
    def database_target_is_test(self) -> bool:
        """True if DATABASE_URL points at the throwaway test cluster or a *test* database."""
        if self.database_url is None:
            return False
        from sqlalchemy.engine import make_url

        url = make_url(self.database_url.get_secret_value())
        return url.port == TEST_CLUSTER_PORT or "test" in (url.database or "").lower()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
