from flask import Flask

from app.config import Config
from app.extensions import db
from app.models import User
from app.routes import main_bp
from app.routes.auth import auth_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    return app