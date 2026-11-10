
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    current_app,
)

from services.payment_service import (
    get_active_plans,
    create_razorpay_order,
)
from services.credit_service import get_remaining_credits
from services.payment_service import verify_and_credit_payment
from admin.plan_service import get_popular_plan_id


payment_bp = Blueprint("payments", __name__)


@payment_bp.route("/credits")
def credits_page():
    if "user_id" not in session:
        from flask import redirect, url_for
        return redirect(
            url_for("auth.login", next=url_for("payments.credits_page"))
        )

    try:
        plans = get_active_plans()
        remaining_credits = get_remaining_credits(session["user_id"])
        popular_plan_id = get_popular_plan_id()

        return render_template(
            "credits.html",
            plans=plans,
            remaining_credits=remaining_credits,
            popular_plan_id=popular_plan_id,
        )

    except Exception:
        current_app.logger.exception("Unable to load credit plans")
        return "Unable to load credit plans. Please try again.", 500


@payment_bp.route("/payments/create-order", methods=["POST"])
def create_order():
    if "user_id" not in session:
        return jsonify({"error": "Please log in first."}), 401

    data = request.get_json(silent=True) or {}
    plan_id = data.get("plan_id")

    if not isinstance(plan_id, int) or isinstance(plan_id, bool) or plan_id <= 0:
        return jsonify({"error": "Invalid credit plan."}), 400

    try:
        order = create_razorpay_order(
            user_id=session["user_id"],
            plan_id=plan_id,
            key_id=current_app.config["RAZORPAY_KEY_ID"],
            key_secret=current_app.config["RAZORPAY_KEY_SECRET"],
        )

        order["key_id"] = current_app.config["RAZORPAY_KEY_ID"]

        return jsonify(order), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception("Razorpay order creation failed")
        return jsonify({
            "error": "Unable to start payment. Please try again."
        }), 500


@payment_bp.route("/payments/verify", methods=["POST"])
def verify_payment():
    if "user_id" not in session:
        return jsonify({"error": "Please log in first."}), 401

    data = request.get_json(silent=True) or {}

    payment_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")

    if not all(
        isinstance(value, str) and value.strip()
        for value in (payment_id, order_id, signature)
    ):
        return jsonify({"error": "Invalid payment details."}), 400

    try:
        result = verify_and_credit_payment(
            user_id=session["user_id"],
            payment_id=payment_id,
            order_id=order_id,
            signature=signature,
            key_id=current_app.config["RAZORPAY_KEY_ID"],
            key_secret=current_app.config["RAZORPAY_KEY_SECRET"],
        )

        return jsonify(result), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception("Payment verification failed")
        return jsonify({
            "error": "Unable to verify payment. Please contact support if money was deducted."
        }), 500
