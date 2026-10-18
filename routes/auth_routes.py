from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app
)
from services.auth_service import register_user, authenticate_user
from email_validator import validate_email, EmailNotValidError

auth_bp = Blueprint("auth", __name__)



@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template(
            "register.html",
            form_data={"username": "", "email": ""}
        )
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    # Preserve only non-sensitive values after a failed submission.
    form_data = {
        "username": username,
        "email": email,
    }

    try:
        if not confirm_password:
            raise ValueError("Please confirm your password.")
        if password != confirm_password:
            raise ValueError("Passwords do not match.")

        # Validate email syntax and DNS/MX configuration on the server.
        # This does not prove mailbox existence or SES sending eligibility.
        try:
            email = validate_email(email, check_deliverability=True).normalized
            domain = email.rsplit("@", 1)[1].lower()

            common_typos = {
                "gmil.com": "gmail.com",
                "gmai.com": "gmail.com",
                "gmail.con": "gmail.com",
                "yaho.com": "yahoo.com",
                "yahoo.con": "yahoo.com",
                "hotmal.com": "hotmail.com",
                "outlok.com": "outlook.com",
                "iclould.com": "icloud.com",
            }

            if domain in common_typos:
                raise ValueError(
                    f"Please check your email domain. Did you mean {common_typos[domain]}?"
                )
        except EmailNotValidError as exc:
            raise ValueError(
                "Please enter a valid email address with a domain configured to receive email."
            ) from exc

        form_data["email"] = email
        register_user(username, email, password)
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Registration failed")
        flash("Registration failed. Please try again.", "error")

    return render_template("register.html", form_data=form_data), 400



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
