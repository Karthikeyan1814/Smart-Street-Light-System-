import logging
import logging.handlers
from pathlib import Path

from .config import BASE_DIR, settings


LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def configure_logging() -> None:
    """
    Configure application-wide logging with a rotating file handler.

    Log format:
        timestamp | level | module | message
    """
    log_path = LOG_DIR / "backend.log"
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO if settings.ENV == "production" else logging.DEBUG)

    # Avoid duplicate handlers on reconfigure
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)

