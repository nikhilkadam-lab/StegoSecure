from flask import Blueprint, jsonify, request, session

from app.extensions import db
from app.models import Admin
from app.utils import normalize_email, verify_password


admin_auth_bp = Blueprint(
    "admin_auth",
    __name__,
    url_prefix="/api/admin",
)


@admin_auth_bp.post("/login")
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    email = normalize_email(data.get("email"))
    password = data.get("password")

    if email is None or not isinstance(password, str):
        return jsonify({"error": "Invalid email or password."}), 401

    admin = db.session.execute(
        db.select(Admin).filter_by(email=email)
    ).scalar_one_or_none()

    if (
        admin is None
        or not admin.is_active
        or not verify_password(admin.password_hash, password)
    ):
        return jsonify({"error": "Invalid email or password."}), 401

    session["admin_id"] = admin.id

    return jsonify(
        {
            "message": "Admin login successful.",
            "admin": {
                "id": admin.id,
                "name": admin.name,
                "email": admin.email,
            },
        }
    )


@admin_auth_bp.post("/logout")
def logout():
    session.pop("admin_id", None)

    return jsonify({"message": "Admin logout successful."})


@admin_auth_bp.get("/me")
def current_admin():
    admin_id = session.get("admin_id")

    if admin_id is None:
        return jsonify({"error": "Admin authentication required."}), 401

    admin = db.session.get(Admin, admin_id)

    if admin is None or not admin.is_active:
        session.pop("admin_id", None)
        return jsonify({"error": "Admin authentication required."}), 401

    return jsonify(
        {
            "admin": {
                "id": admin.id,
                "name": admin.name,
                "email": admin.email,
            }
        }
    )