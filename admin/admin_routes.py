from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
)

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from db import get_db_connection
from utils.validators import normalize_email
from .admin_auth import admin_required, get_active_admin


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/secure-console-x7k9",
)

password_hasher = PasswordHasher()


@admin_bp.route("/", methods=["GET", "POST"])
def login():

    # If an active admin is already logged in, open the dashboard.
    if request.method == "GET" and session.get("admin_id"):
        try:
            admin = get_active_admin(session["admin_id"])

            if admin:
                return redirect(url_for("admin.dashboard"))

        except Exception:
            current_app.logger.exception("Admin session check failed")

        session.pop("admin_id", None)
        session.pop("admin_username", None)
        session.pop("admin_email", None)

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:
            email = normalize_email(email)

            if not password:
                raise ValueError("Invalid credentials.")

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, username, email, password_hash, is_active
                FROM admins
                WHERE email = %s
                LIMIT 1
                """,
                (email,),
            )

            admin = cursor.fetchone()

            if not admin or not admin["is_active"]:
                raise ValueError("Invalid credentials.")

            try:
                password_hasher.verify(
                    admin["password_hash"],
                    password,
                )

            except (
                VerifyMismatchError,
                VerificationError,
                InvalidHashError,
            ):
                raise ValueError("Invalid credentials.")

            # Set admin session without clearing the user session.
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            session["admin_email"] = admin["email"]

            return redirect(url_for("admin.dashboard"))

        except ValueError:
            flash("Invalid email or password.", "error")

        except Exception:
            current_app.logger.exception("Admin login failed")
            flash("Unable to log in. Please try again.", "error")

        finally:
            if cursor:
                cursor.close()

            if connection and connection.is_connected():
                connection.close()

    return render_template("admin/login.html")


@admin_bp.route("/dashboard")
@admin_required
def dashboard():

    return render_template(
        "admin/dashboard.html",
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_email", None)

    flash("Admin logged out successfully.", "success")

    return redirect(url_for("admin.login"))