import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from the project directory.
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

        # Razorpay payment configuration
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("COOKIE_SECURE", "false").lower() == "true"
    )

    PERMANENT_SESSION_LIFETIME = 7200

    # Maximum total size of one multipart request.
    # Default: 20 MB. Can be changed using MAX_UPLOAD_MB in .env.
    MAX_CONTENT_LENGTH = (
        int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
    )