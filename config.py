"""Application configuration. Secrets come from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # The secret key signs session cookies. Set a real one in .env.
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-key-change-me"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(BASE_DIR / "instance" / "smart_student_hub.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads (used from Stage 3). Kept outside /static so files are private.
    # A relative path in .env is resolved against the project folder, so saving and
    # downloading always use the same absolute location.
    UPLOAD_FOLDER = str((BASE_DIR / (os.environ.get("UPLOAD_FOLDER") or "instance/uploads")).resolve())
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "txt"}

    # All deadline calculations use this timezone.
    APP_TIMEZONE = "Asia/Kolkata"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-key"
