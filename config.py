import os
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    """Base application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "medilens-ai-default-insecure-secret-key-change-me")
    TEMPLATES_AUTO_RELOAD = True

    # MySQL Configuration
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "medilens")

    _password_encoded = urllib.parse.quote_plus(MYSQL_PASSWORD)
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{_password_encoded}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Uploads
    UPLOAD_FOLDER = BASE_DIR / "uploads" / "prescriptions"
    PROCESSED_FOLDER = BASE_DIR / "uploads" / "processed"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

    # External APIs
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    MAPS_API_KEY = os.getenv("MAPS_API_KEY", "")

    # Tesseract and Poppler configuration
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    POPPLER_PATH = os.getenv("POPPLER_PATH", r"C:\poppler\poppler-26.02.0\Library\bin")

    # Logging
    LOG_DIR = BASE_DIR / "logs"
    LOG_FILE = LOG_DIR / "app.log"


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    WTF_CSRF_ENABLED = False
