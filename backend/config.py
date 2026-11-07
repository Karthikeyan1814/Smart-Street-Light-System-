import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
VIDEO_STORAGE_DIR = STORAGE_DIR / "videos"
DB_PATH = STORAGE_DIR / "database.db"

# Ensure storage directories exist at import time
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    """
    Central configuration for the backend service.

    Values are read from environment variables with sensible defaults
    so the system can run locally out-of-the-box and be overridden in
    Docker / cloud environments.
    """

    # Environment
    ENV: str = os.getenv("ENV", "development").lower()

    # Core server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Security / auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    API_KEY: str = os.getenv("API_KEY", "hello-from-pi-lets-make-it-work")

    # LLM configuration
    USE_REAL_LLM: bool = os.getenv("USE_REAL_LLM", "false").lower() == "true"
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE")  # optional custom base URL
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Database
    SQLITE_PATH: str = str(DB_PATH)

    # CORS / frontend
    CORS_ALLOW_ORIGINS: list[str] = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5000,http://localhost:5173,http://127.0.0.1:5000",
    ).split(",")

    # Rate limiting (per IP per minute)
    ALERT_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("ALERT_RATE_LIMIT_PER_MINUTE", "120"))

    # System version
    SYSTEM_VERSION: str = os.getenv("SYSTEM_VERSION", "4.0.0-final")

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


settings = Settings()

