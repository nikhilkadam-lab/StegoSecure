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
from services.auth_service import (
    register_user,
    start_registration,
    complete_registration,
    authenticate_user,
    get_user_profile,
    update_username,
    verify_current_password,
    update_user_password,
    start_password_reset,
    complete_password_reset,
)
from services.credit_service import get_remaining_credits
from services.payment_service import get_user_payment_history
from email_validator import validate_email, EmailNotValidError
from services.otp_service import issue_otp, verify_otp


auth_bp = Blueprint("auth", __name__)



@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template(
            "register.html",
            form_data={"username": "", "email": ""},
            otp_sent=False,
        )

    action = request.form.get("action", "send_otp")
    email = request.form.get("email", "").strip()

    form_data = {
        "username": request.form.get("username", "").strip(),
        "email": email,
    }

    try:
        if action == "send_otp":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not confirm_password:
                raise ValueError("Please confirm your password.")

            if password != confirm_password:
                raise ValueError("Passwords do not match.")

            try:
                email = validate_email(
                    email,
                    check_deliverability=True,
                ).normalized

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
                        f"Please check your email domain. "
                        f"Did you mean {common_typos[domain]}?"
                    )

            except EmailNotValidError as exc:
                raise ValueError(
                    "Please enter a valid email address with a domain "
                    "configured to receive email."
                ) from exc

            form_data["email"] = email

            start_registration(
                username=form_data["username"],
                email=email,
                password=password,
            )

            flash(
                "Verification code sent to your email address.",
                "success",
            )

            return render_template(
                "register.html",
                form_data=form_data,
                otp_sent=True,
            )

        elif action == "verify_otp":
            otp = request.form.get("otp", "").strip()

            complete_registration(email, otp)

            flash(
                "Email verified and account created successfully. "
                "You can now log in.",
                "success",
            )
            return redirect(url_for("auth.login"))

        else:
            raise ValueError("Invalid registration action.")

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Registration failed")
        flash("Registration failed. Please try again.", "error")

    return render_template(
        "register.html",
        form_data=form_data,
        otp_sent=(action == "verify_otp"),
    ), 400


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.form.get("next") or request.args.get("next", "")

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            user = authenticate_user(email, password)

            session.pop("user_id", None)
            session.pop("username", None)
            session.pop("email", None)

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            # Only allow local relative destinations.
            if (
                next_url.startswith("/")
                and not next_url.startswith("//")
                and "\\" not in next_url
            ):
                return redirect(next_url)

            return redirect(url_for("auth.dashboard"))

        except ValueError:
            flash("Invalid email or password.", "error")

        except Exception:
            current_app.logger.exception("Login failed")
            flash("Login failed. Please try again.", "error")

    return render_template("login.html", next_url=next_url)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template(
            "forgot_password.html",
            step=session.get("password_reset_step", "email"),
            email=session.get("password_reset_email", ""),
        )

    action = request.form.get("action", "").strip()

    try:
        if action == "send_otp":
            email = start_password_reset(
                request.form.get("email", "").strip()
            )

            session["password_reset_email"] = email
            session["password_reset_step"] = "otp"
            session.pop("password_reset_challenge_id", None)

            flash(
                "If an active account exists for that email, "
                "a verification code has been sent.",
                "success",
            )

            return render_template(
                "forgot_password.html",
                step="otp",
                email=email,
            )

        elif action == "verify_otp":
            email = session.get("password_reset_email")

            if not email or session.get("password_reset_step") != "otp":
                raise ValueError("Please start the password reset process again.")

            result = verify_otp(
                email=email,
                purpose="user_password_reset",
                submitted_otp=request.form.get("otp", "").strip(),
            )

            session["password_reset_challenge_id"] = result["challenge_id"]
            session["password_reset_step"] = "reset"

            flash("Email verified. You can now set a new password.", "success")

            return render_template(
                "forgot_password.html",
                step="reset",
                email=email,
            )

        elif action == "reset_password":
            email = session.get("password_reset_email")
            challenge_id = session.get("password_reset_challenge_id")

            if (
                not email
                or not challenge_id
                or session.get("password_reset_step") != "reset"
            ):
                raise ValueError("Please verify your email again.")

            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not confirm_password:
                raise ValueError("Please confirm your new password.")

            if new_password != confirm_password:
                raise ValueError("Passwords do not match.")

            complete_password_reset(
                email=email,
                challenge_id=challenge_id,
                new_password=new_password,
            )

            session.pop("password_reset_email", None)
            session.pop("password_reset_step", None)
            session.pop("password_reset_challenge_id", None)

            flash(
                "Your password has been reset successfully. Please log in.",
                "success",
            )
            return redirect(url_for("auth.login"))

        else:
            raise ValueError("Invalid password reset action.")

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Password reset failed")
        flash(
            "Unable to process your request. Please try again.",
            "error",
        )

    return render_template(
        "forgot_password.html",
        step=session.get("password_reset_step", "email"),
        email=session.get("password_reset_email", ""),
    ), 400

@auth_bp.route("/home")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        remaining_credits = get_remaining_credits(session["user_id"])
    
    except Exception:
        current_app.logger.exception(
            "Unable to retrieve encryption credits for user_id=%s",
            session["user_id"],
        )
        remaining_credits = None

    return render_template(
        "home.html",
        banner_url=url_for("site_banner"),
        remaining_credits=remaining_credits,
    )


@auth_bp.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        user = get_user_profile(session["user_id"])

        if not user:
            session.pop("user_id", None)
            session.pop("username", None)
            session.pop("email", None)

            flash("Your account could not be found. Please log in again.", "error")
            return redirect(url_for("auth.login"))

        remaining_credits = get_remaining_credits(session["user_id"])
        payment_history = get_user_payment_history(session["user_id"])

        return render_template(
            "profile.html",
            user=user,
            remaining_credits=remaining_credits,
            payment_history=payment_history,
        )

    except Exception:
        current_app.logger.exception("Unable to load user profile")
        flash("Unable to load your profile. Please try again.", "error")
        return redirect(url_for("auth.dashboard"))

@auth_bp.route("/profile/username", methods=["POST"])
def change_username():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    new_username = request.form.get("new_username", "").strip()

    try:
        updated_username = update_username(
            session["user_id"],
            new_username,
        )

        session["username"] = updated_username

        flash("Username updated successfully.", "success")

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Username update failed")
        flash("Unable to update username. Please try again.", "error")

    return redirect(url_for("auth.profile"))

@auth_bp.route("/profile/password", methods=["POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new_password = request.form.get("confirm_new_password", "")

    try:
        if not verify_current_password(
            session["user_id"],
            current_password,
        ):
            raise ValueError("Your current password is incorrect.")

        if not confirm_new_password:
            raise ValueError("Please confirm your new password.")

        if new_password != confirm_new_password:
            raise ValueError("New passwords do not match.")

        update_user_password(
            session["user_id"],
            new_password,
        )

        flash("Password updated successfully.", "success")

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Password update failed")
        flash("Unable to update password. Please try again.", "error")

    return redirect(url_for("auth.profile", panel="password"))


@auth_bp.route("/profile/password-reset/send-otp", methods=["POST"])
def profile_password_reset_send_otp():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    try:
        user = get_user_profile(session["user_id"])

        if not user or not user.get("email"):
            raise ValueError("Unable to find your registered email address.")

        email = user["email"]

        result = issue_otp(
            email=email,
            purpose="user_password_reset",
        )

        session["profile_password_reset_email"] = email
        session["profile_password_reset_challenge_id"] = result["challenge_id"]
        session["profile_password_reset_step"] = "otp"

        flash("Verification code sent to your registered email address.", "success")

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Profile password-reset OTP sending failed")
        flash("Unable to send the verification code. Please try again.", "error")

    return redirect(url_for("auth.profile", panel="forgot"))


@auth_bp.route("/profile/password-reset/verify-otp", methods=["POST"])
def profile_password_reset_verify_otp():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    email = session.get("profile_password_reset_email")
    expected_challenge_id = session.get("profile_password_reset_challenge_id")

    if (
        not email
        or not expected_challenge_id
        or session.get("profile_password_reset_step") != "otp"
    ):
        flash("Please request a new verification code.", "error")
        return redirect(url_for("auth.profile", panel="forgot"))

    try:
        user = get_user_profile(session["user_id"])

        if not user or user.get("email") != email:
            raise ValueError("Your registered email has changed. Please start again.")

        result = verify_otp(
            email=email,
            purpose="user_password_reset",
            submitted_otp=request.form.get("otp", "").strip(),
        )

        if str(result["challenge_id"]) != str(expected_challenge_id):
            raise ValueError("This verification code is no longer valid. Please request a new one.")

        session["profile_password_reset_step"] = "reset"

        flash("Email verified. You can now set a new password.", "success")

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Profile password-reset OTP verification failed")
        flash("Unable to verify the code. Please try again.", "error")

    return redirect(url_for("auth.profile", panel="forgot"))


@auth_bp.route("/profile/password-reset/reset", methods=["POST"])
def profile_password_reset_reset():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    email = session.get("profile_password_reset_email")
    challenge_id = session.get("profile_password_reset_challenge_id")

    if (
        not email
        or not challenge_id
        or session.get("profile_password_reset_step") != "reset"
    ):
        flash("Please verify your email before setting a new password.", "error")
        return redirect(url_for("auth.profile", panel="forgot"))

    try:
        user = get_user_profile(session["user_id"])

        if not user or user.get("email") != email:
            raise ValueError("Your registered email has changed. Please start again.")

        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not confirm_password:
            raise ValueError("Please confirm your new password.")

        if new_password != confirm_password:
            raise ValueError("Passwords do not match.")

        complete_password_reset(
            email=email,
            challenge_id=challenge_id,
            new_password=new_password,
        )

        session.pop("profile_password_reset_email", None)
        session.pop("profile_password_reset_challenge_id", None)
        session.pop("profile_password_reset_step", None)

        flash("Your password has been reset successfully.", "success")
        return redirect(url_for("auth.profile"))

    except ValueError as exc:
        flash(str(exc), "error")

    except Exception:
        current_app.logger.exception("Profile password reset failed")
        flash("Unable to reset your password. Please try again.", "error")

    return redirect(url_for("auth.profile", panel="forgot"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("email", None)

    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
