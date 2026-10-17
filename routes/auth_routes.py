from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from services.auth_service import register_user, authenticate_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            register_user(username, email, password)
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))

        except ValueError as exc:
            flash(str(exc), "error")

        except Exception:
            flash("Registration failed. Please try again.", "error")

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            user = authenticate_user(email, password)

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]

            return redirect(url_for("auth.dashboard"))

        except ValueError:
            flash("Invalid email or password.", "error")

        except Exception:
            flash("Login failed. Please try again.", "error")

    return render_template("login.html")


@auth_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    return render_template("dashboard.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
