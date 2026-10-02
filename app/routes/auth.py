from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import User
from app.utils import hash_password, normalize_email, validate_password


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    email = normalize_email(data.get("email"))
    password = data.get("password")

    if email is None:
        return jsonify({"error": "Enter a valid email address."}), 400

    password_valid, password_error = validate_password(password)

    if not password_valid:
        return jsonify({"error": password_error}), 400

    existing_user = db.session.execute(
        db.select(User).filter_by(email=email)
    ).scalar_one_or_none()

    if existing_user is not None:
        return jsonify({"error": "An account with this email already exists."}), 409

    user = User(
        email=email,
        password_hash=hash_password(password),
        is_admin=False,
    )

    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Registration successful.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                },
            }
        ),
        201,
    )
