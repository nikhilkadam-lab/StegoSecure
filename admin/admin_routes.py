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
from .dashboard_service import get_dashboard_statistics
from flask import jsonify
from .user_service import (
    get_users,
    update_user_status,
    update_user_credits,
)

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

    dashboard_data = get_dashboard_statistics()

    return render_template(
        "admin/dashboard.html",
        admin_username=session.get("admin_username"),
        statistics=dashboard_data["statistics"],
        recent_transactions=dashboard_data["recent_transactions"],
        recent_users=dashboard_data["recent_users"],
    )


@admin_bp.route("/users")
@admin_required
def users():
    return render_template(
        "admin/users.html",
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/users/api", methods=["GET"])
@admin_required
def users_api():

    try:
        search = request.args.get("search", "").strip()
        status = request.args.get("status", "all")
        cursor_value = request.args.get("cursor")

        if len(search) > 100:
            return jsonify({
                "success": False,
                "message": "Search query is too long."
            }), 400

        before_id = None

        if cursor_value:
            try:
                before_id = int(cursor_value)
                if before_id < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "message": "Invalid pagination cursor."
                }), 400

        result = get_users(
            limit=15,
            before_id=before_id,
            search=search,
            status=status,
        )

        return jsonify({
            "success": True,
            **result,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 400

    except Exception:
        current_app.logger.exception(
            "Admin user listing failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load users."
        }), 500



@admin_bp.route("/users/<int:user_id>/status", methods=["POST"])
@admin_required
def update_user_status_api(user_id):

    try:
        data = request.get_json(silent=True) or {}
        is_active = data.get("is_active")

        if not isinstance(is_active, bool):
            return jsonify({
                "success": False,
                "message": "Invalid account status."
            }), 400

        update_user_status(user_id, is_active)

        return jsonify({
            "success": True,
            "message": (
                "Account enabled successfully."
                if is_active
                else "Account disabled successfully."
            ),
            "is_active": is_active,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception(
            "Admin account status update failed"
        )
        return jsonify({
            "success": False,
            "message": "Unable to update account status."
        }), 500


@admin_bp.route("/users/<int:user_id>/credits", methods=["POST"])
@admin_required
def update_user_credits_api(user_id):

    try:
        data = request.get_json(silent=True) or {}
        credits = data.get("remaining_credits")

        if isinstance(credits, bool):
            raise ValueError("Invalid credit balance.")

        if not isinstance(credits, int):
            raise ValueError("Credit balance must be a whole number.")

        update_user_credits(user_id, credits)

        return jsonify({
            "success": True,
            "message": "Remaining credits updated successfully.",
            "remaining_credits": credits,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception(
            "Admin credit balance update failed"
        )
        return jsonify({
            "success": False,
            "message": "Unable to update credits."
        }), 500



@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_email", None)

    flash("Admin logged out successfully.", "success")

    return redirect(url_for("admin.login"))