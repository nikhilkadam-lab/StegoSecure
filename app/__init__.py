from flask import Flask

from app.config import Config
from app.extensions import db
from app.routes import main_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(main_bp)

    return app