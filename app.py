import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    redirect,
    url_for,
    render_template,
    send_from_directory,
    current_app,
)
from flask_wtf.csrf import CSRFProtect
from services.site_service import get_active_banner

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY is missing from the .env file.")

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower()
    == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
)

CSRFProtect(app)

from routes.auth_routes import auth_bp

app.register_blueprint(auth_bp)


@app.route("/")
def home():
    return render_template(
        "home.html",
        banner_url=url_for("site_banner"),
    )


@app.route("/site-banner")
def site_banner():
    filename = get_active_banner()

    if filename:
        banner_directory = Path(app.instance_path) / "banners"
        banner_path = banner_directory / filename

        if banner_path.is_file():
            return send_from_directory(
                str(banner_directory),
                filename,
            )

    # Default banner when no admin banner exists.
    return send_from_directory(
        str(BASE_DIR),
        "StegoSecure Banner.png",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
