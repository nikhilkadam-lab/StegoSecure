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
from .plan_service import (
    get_all_plans,
    get_popular_plan_id,
    create_plan,
    update_plan,
    update_plan_status,
    delete_plan,
)
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

    popular_plan_id = get_popular_plan_id()
    plans = get_all_plans()

    popular_plan = next(
        (
            plan for plan in plans
            if plan["id"] == popular_plan_id
        ),
        None
    )

    return render_template(
        "admin/dashboard.html",
        admin_username=session.get("admin_username"),
        statistics=dashboard_data["statistics"],
        recent_transactions=dashboard_data["recent_transactions"],
        recent_users=dashboard_data["recent_users"],
        popular_plan=popular_plan,
    )


@admin_bp.route("/users")
@admin_required
def users():
    return render_template(
        "admin/users.html",
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/credit-plans")
@admin_required
def credit_plans():
    return render_template(
        "admin/credit_plans.html",
        admin_username=session.get("admin_username"),
        plans=get_all_plans(),
        popular_plan_id=get_popular_plan_id(),
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



@admin_bp.route("/credit-plans/api", methods=["GET"])
@admin_required
def credit_plans_api():
    try:
        plans = get_all_plans()
        popular_plan_id = get_popular_plan_id()

        return jsonify({
            "success": True,
            "plans": plans,
            "popular_plan_id": popular_plan_id,
        })

    except Exception:
        current_app.logger.exception("Admin credit plans listing failed")
        return jsonify({
            "success": False,
            "message": "Unable to load credit plans."
        }), 500


@admin_bp.route("/credit-plans", methods=["POST"])
@admin_required
def create_plan_api():
    try:
        data = request.get_json(silent=True) or {}

        name = data.get("name")
        price = data.get("price")
        credits = data.get("credits")
        is_popular = data.get("is_popular", False)

        if isinstance(credits, bool) or not isinstance(credits, int):
            raise ValueError("Credits must be a whole number.")

        if not isinstance(is_popular, bool):
            raise ValueError("Invalid Popular selection.")

        plan_id = create_plan(name, price, credits, is_popular)

        return jsonify({
            "success": True,
            "message": "Credit plan created successfully.",
            "plan_id": plan_id,
            "popular_plan_id": get_popular_plan_id(),
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception("Admin credit plan creation failed")
        return jsonify({
            "success": False,
            "message": "Unable to create credit plan."
        }), 500


@admin_bp.route("/credit-plans/<int:plan_id>", methods=["PUT"])
@admin_required
def update_plan_api(plan_id):
    try:
        data = request.get_json(silent=True) or {}

        name = data.get("name")
        price = data.get("price")
        credits = data.get("credits")
        is_popular = data.get("is_popular", False)

        if isinstance(credits, bool) or not isinstance(credits, int):
            raise ValueError("Credits must be a whole number.")

        if not isinstance(is_popular, bool):
            raise ValueError("Invalid Popular selection.")

        update_plan(plan_id, name, price, credits, is_popular)

        return jsonify({
            "success": True,
            "message": "Credit plan updated successfully.",
            "popular_plan_id": get_popular_plan_id(),
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception("Admin credit plan update failed")
        return jsonify({
            "success": False,
            "message": "Unable to update credit plan."
        }), 500


@admin_bp.route("/credit-plans/<int:plan_id>/status", methods=["POST"])
@admin_required
def update_plan_status_api(plan_id):
    try:
        data = request.get_json(silent=True) or {}
        is_active = data.get("is_active")

        if not isinstance(is_active, bool):
            raise ValueError("Invalid plan status.")

        update_plan_status(plan_id, is_active)

        return jsonify({
            "success": True,
            "message": (
                "Plan enabled successfully."
                if is_active
                else "Plan disabled successfully."
            ),
            "is_active": is_active,
            "popular_plan_id": get_popular_plan_id(),
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception("Admin credit plan status update failed")
        return jsonify({
            "success": False,
            "message": "Unable to update plan status."
        }), 500


@admin_bp.route("/credit-plans/<int:plan_id>", methods=["DELETE"])
@admin_required
def delete_plan_api(plan_id):
    try:
        delete_plan(plan_id)

        return jsonify({
            "success": True,
            "message": "Credit plan deleted successfully.",
            "popular_plan_id": get_popular_plan_id(),
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception("Admin credit plan deletion failed")
        return jsonify({
            "success": False,
            "message": "Unable to delete credit plan."
        }), 500



@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_email", None)

    flash("Admin logged out successfully.", "success")

    return redirect(url_for("admin.login"))