from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    send_from_directory,
)

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from db import get_db_connection
from services.otp_service import (
    issue_otp,
    verify_otp,
    consume_verified_otp,
)
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
from .revenue_service import (
    get_revenue_summary,
    get_transactions,
)
from .settings_service import (
    get_default_encryption_limit,
    update_default_encryption_limit,
    list_uploaded_banners,
    save_uploaded_banner,
    activate_banner,
    deactivate_banner,
    delete_uploaded_banner,
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

        action = request.form.get("action", "password").strip()

        # STEP 1: Verify admin email and password, then send OTP.
        if action == "password":

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

                # Remove previous authenticated and pending admin state.
                session.pop("admin_id", None)
                session.pop("admin_username", None)
                session.pop("admin_email", None)

                session.pop("admin_pending_id", None)
                session.pop("admin_pending_email", None)
                session.pop("admin_otp_challenge_id", None)

                # Send OTP only after successful password verification.
                result = issue_otp(
                    email=admin["email"],
                    purpose="admin_login",
                )

                # Store pending identity, NOT authenticated admin access.
                session["admin_pending_id"] = admin["id"]
                session["admin_pending_email"] = admin["email"]
                session["admin_otp_challenge_id"] = result["challenge_id"]

                flash(
                    "Verification code sent to your registered admin email.",
                    "success",
                )

            except ValueError as exc:
                flash(str(exc), "error")

            except Exception:
                current_app.logger.exception("Admin login failed")
                flash("Unable to log in. Please try again.", "error")

            finally:
                if cursor:
                    cursor.close()

                if connection and connection.is_connected():
                    connection.close()

        # STEP 2: Verify OTP and only then create the admin session.
        elif action == "verify_otp":

            email = session.get("admin_pending_email")
            admin_id = session.get("admin_pending_id")
            expected_challenge_id = session.get("admin_otp_challenge_id")

            if not email or not admin_id or not expected_challenge_id:
                flash(
                    "Please enter your admin email and password again.",
                    "error",
                )
                return redirect(url_for("admin.login"))

            try:
                result = verify_otp(
                    email=email,
                    purpose="admin_login",
                    submitted_otp=request.form.get("otp", "").strip(),
                )

                if str(result["challenge_id"]) != str(expected_challenge_id):
                    raise ValueError(
                        "This verification code is no longer valid. "
                        "Please log in again."
                    )

                # Recheck that the admin account is still active.
                admin = get_active_admin(admin_id)

                if not admin:
                    session.pop("admin_pending_id", None)
                    session.pop("admin_pending_email", None)
                    session.pop("admin_otp_challenge_id", None)

                    raise ValueError(
                        "Your admin account is inactive or unavailable."
                    )

                # Consume the verified OTP so it cannot be reused.
                if not consume_verified_otp(expected_challenge_id):
                    raise ValueError(
                        "Your verification code has expired. Please log in again."
                    )

                # OTP verified: create the authenticated admin session.
                session.pop("admin_pending_id", None)
                session.pop("admin_pending_email", None)
                session.pop("admin_otp_challenge_id", None)

                session["admin_id"] = admin["id"]
                session["admin_username"] = admin["username"]
                session["admin_email"] = admin["email"]

                flash("Admin login verified successfully.", "success")

                return redirect(url_for("admin.dashboard"))

            except ValueError as exc:
                flash(str(exc), "error")

            except Exception:
                current_app.logger.exception("Admin OTP verification failed")
                flash(
                    "Unable to verify the code. Please try again.",
                    "error",
                )

        else:
            flash("Invalid login action.", "error")

    return render_template(
        "admin/login.html",
        otp_sent=bool(session.get("admin_otp_challenge_id")),
        admin_email=session.get("admin_pending_email", ""),
    )


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


@admin_bp.route("/revenue")
@admin_required
def revenue():
    return render_template(
        "admin/revenue.html",
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/revenue/api/summary", methods=["GET"])
@admin_required
def revenue_summary_api():
    try:
        summary = get_revenue_summary()

        return jsonify({
            "success": True,
            "summary": {
                key: float(value)
                for key, value in summary.items()
            },
        })

    except Exception:
        current_app.logger.exception(
            "Admin revenue summary failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load revenue summary.",
        }), 500


@admin_bp.route("/revenue/api/transactions", methods=["GET"])
@admin_required
def revenue_transactions_api():
    try:
        status = request.args.get("status", "success")
        search = request.args.get("search", "").strip()
        cursor_value = request.args.get("cursor")

        if len(search) > 100:
            return jsonify({
                "success": False,
                "message": "Search query is too long.",
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
                    "message": "Invalid pagination cursor.",
                }), 400

        result = get_transactions(
            status=status,
            limit=15,
            before_id=before_id,
            search=search,
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
            "Admin transaction listing failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load transactions.",
        }), 500



# ============================================================
# SYSTEM SETTINGS
# ============================================================

@admin_bp.route("/settings")
@admin_required
def settings():
    return render_template(
        "admin/settings.html",
        admin_username=session.get("admin_username"),
    )


@admin_bp.route("/settings/api/limit", methods=["GET"])
@admin_required
def settings_limit_api():
    try:
        return jsonify({
            "success": True,
            "default_encryption_limit": get_default_encryption_limit(),
        })
    except Exception:
        current_app.logger.exception("Unable to load default encryption limit")
        return jsonify({
            "success": False,
            "message": "Unable to load encryption limit.",
        }), 500


@admin_bp.route("/settings/api/limit", methods=["POST"])
@admin_required
def update_settings_limit_api():
    try:
        data = request.get_json(silent=True) or {}
        value = data.get("default_encryption_limit")

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Enter a valid whole-number encryption limit.")

        update_default_encryption_limit(value)

        return jsonify({
            "success": True,
            "message": "Default encryption limit updated successfully.",
            "default_encryption_limit": value,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 400

    except Exception:
        current_app.logger.exception("Default encryption limit update failed")
        return jsonify({
            "success": False,
            "message": "Unable to update encryption limit.",
        }), 500


@admin_bp.route("/settings/api/banners", methods=["GET"])
@admin_required
def settings_banners_api():
    try:
        banners = list_uploaded_banners(current_app.instance_path)

        return jsonify({
            "success": True,
            "banners": banners,
        })

    except Exception:
        current_app.logger.exception("Unable to load admin banners")
        return jsonify({
            "success": False,
            "message": "Unable to load banners.",
        }), 500


@admin_bp.route("/settings/api/banners", methods=["POST"])
@admin_required
def upload_banner_api():
    try:
        uploaded_file = request.files.get("banner")

        filename = save_uploaded_banner(
            uploaded_file,
            current_app.instance_path,
        )

        return jsonify({
            "success": True,
            "message": "Banner uploaded successfully.",
            "filename": filename,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 400

    except Exception:
        current_app.logger.exception("Admin banner upload failed")
        return jsonify({
            "success": False,
            "message": "Unable to upload banner.",
        }), 500


@admin_bp.route(
    "/settings/api/banners/<filename>/status",
    methods=["POST"],
)
@admin_required
def update_banner_status_api(filename):
    try:
        data = request.get_json(silent=True) or {}
        is_active = data.get("is_active")

        if not isinstance(is_active, bool):
            raise ValueError("Invalid banner status.")

        if is_active:
            activate_banner(filename, current_app.instance_path)
            message = "Banner activated successfully."
        else:
            deactivate_banner(filename, current_app.instance_path)
            message = "Banner deactivated. Default banner will be displayed."

        return jsonify({
            "success": True,
            "message": message,
            "is_active": is_active,
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 400

    except Exception:
        current_app.logger.exception("Admin banner status update failed")
        return jsonify({
            "success": False,
            "message": "Unable to update banner status.",
        }), 500


@admin_bp.route(
    "/settings/api/banners/<filename>",
    methods=["DELETE"],
)
@admin_required
def delete_banner_api(filename):
    try:
        delete_uploaded_banner(filename, current_app.instance_path)

        return jsonify({
            "success": True,
            "message": "Banner deleted successfully.",
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 400

    except Exception:
        current_app.logger.exception("Admin banner deletion failed")
        return jsonify({
            "success": False,
            "message": "Unable to delete banner.",
        }), 500


@admin_bp.route("/settings/api/banners/<filename>/image", methods=["GET"])
@admin_required
def preview_banner_api(filename):
    allowed_extensions = {".png", ".jpg", ".jpeg", ".webp"}

    if (
        filename != Path(filename).name
        or not filename.startswith("admin_")
        or Path(filename).suffix.lower() not in allowed_extensions
    ):
        return jsonify({
            "success": False,
            "message": "Invalid banner filename.",
        }), 400

    banner_directory = Path(current_app.instance_path) / "banners"

    return send_from_directory(
        str(banner_directory),
        filename,
    )


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_email", None)

    flash("Admin logged out successfully.", "success")

    return redirect(url_for("admin.login"))