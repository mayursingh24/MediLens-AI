import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(app):
    """Configure structured logging for the application."""
    log_dir = Path(app.config.get("LOG_DIR", Path(__file__).resolve().parent.parent.parent / "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logger = logging.getLogger("medilens")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if already added
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s (%(funcName)s:%(lineno)d): %(message)s"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    app.logger = logger
    return logger

def get_logger():
    """Retrieve the medilens logger."""
    return logging.getLogger("medilens")
