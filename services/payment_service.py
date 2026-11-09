
from decimal import Decimal
from uuid import uuid4

import razorpay

from db import get_db_connection
import mysql.connector
from decimal import Decimal


def get_active_plans():
    """Return credit plans currently available for purchase."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, name, price, encryptions
            FROM plans
            WHERE is_active = 1
            ORDER BY price ASC
            """
        )

        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def create_razorpay_order(user_id, plan_id, key_id, key_secret):
    """Create a Razorpay order and save its pending payment record."""

    connection = None
    cursor = None

    try:
        # 1. Retrieve the selected active plan.
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, name, price, encryptions
            FROM plans
            WHERE id = %s AND is_active = 1
            """,
            (plan_id,),
        )

        plan = cursor.fetchone()

        cursor.close()
        cursor = None
        connection.close()
        connection = None

        if not plan:
            raise ValueError("This credit plan is no longer available.")

        # 2. Convert the plan price into paise.
        amount = Decimal(str(plan["price"]))
        amount_paise = int(amount * 100)

        if amount_paise <= 0:
            raise ValueError("Invalid credit plan amount.")

        # 3. Create the Razorpay order.
        client = razorpay.Client(
            auth=(key_id, key_secret)
        )

        receipt = uuid4().hex

        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "user_id": str(user_id),
                "plan_id": str(plan["id"]),
            },
        })

        # 4. Save the pending payment with purchase snapshots.
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO payments (
                user_id,
                plan_id,
                razorpay_order_id,
                amount,
                status,
                plan_name_snapshot,
                credits_snapshot
            )
            VALUES (%s, %s, %s, %s, 'pending', %s, %s)
            """,
            (
                user_id,
                plan["id"],
                order["id"],
                amount,
                plan["name"],
                plan["encryptions"],
            ),
        )

        connection.commit()

        return {
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "plan_name": plan["name"],
            "credits": plan["encryptions"],
        }

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def verify_and_credit_payment(
    user_id,
    payment_id,
    order_id,
    signature,
    key_id,
    key_secret,
):
    """Verify Razorpay payment and atomically credit the user."""

    client = razorpay.Client(auth=(key_id, key_secret))

    # 1. Verify Razorpay signature.
    try:
        client.utility.verify_payment_signature({
            "razorpay_payment_id": payment_id,
            "razorpay_order_id": order_id,
            "razorpay_signature": signature,
        })
    except Exception:
        raise ValueError("Payment verification failed.")

    # 2. Fetch payment details directly from Razorpay.
    try:
        payment = client.payment.fetch(payment_id)
    except Exception:
        raise ValueError("Unable to confirm payment status.")

    if payment.get("order_id") != order_id:
        raise ValueError("Payment order mismatch.")

    if payment.get("status") != "captured":
        raise ValueError("Payment has not been captured yet.")

    if payment.get("currency") != "INR":
        raise ValueError("Invalid payment currency.")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # 3. Lock the pending payment record.
        cursor.execute(
            """
            SELECT *
            FROM payments
            WHERE razorpay_order_id = %s
              AND user_id = %s
            FOR UPDATE
            """,
            (order_id, user_id),
        )

        record = cursor.fetchone()

        if not record:
            raise ValueError("Payment order not found.")

        # 4. Prevent duplicate credit additions.
        if record["status"] == "success":
            if record["payment_id"] == payment_id:
                return {
                    "success": True,
                    "message": "Payment already verified.",
                    "credits": record["credits_snapshot"],
                }

            raise ValueError("This order has already been processed.")

        if record["status"] != "pending":
            raise ValueError("This payment cannot be processed.")

        expected_amount = int(
            Decimal(str(record["amount"])) * 100
        )

        if payment.get("amount") != expected_amount:
            raise ValueError("Payment amount mismatch.")

        if not record["credits_snapshot"]:
            raise ValueError("Invalid purchased credit quantity.")

        # 5. Add credits to the existing user balance.
        cursor.execute(
            """
            UPDATE encryption_limits
            SET remaining_attempts = remaining_attempts + %s
            WHERE user_id = %s
            """,
            (record["credits_snapshot"], user_id),
        )

        if cursor.rowcount != 1:
            raise ValueError("User credit account not found.")

        # 6. Mark payment successful in the same transaction.
        cursor.execute(
            """
            UPDATE payments
            SET payment_id = %s,
                status = 'success'
            WHERE id = %s
              AND status = 'pending'
            """,
            (payment_id, record["id"]),
        )

        if cursor.rowcount != 1:
            raise ValueError("Payment could not be confirmed.")

        connection.commit()

        return {
            "success": True,
            "message": "Payment verified successfully.",
            "credits": record["credits_snapshot"],
        }

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def get_user_payment_history(user_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                COALESCE(plan_name_snapshot, 'Credit Plan') AS plan_name,
                credits_snapshot AS credits,
                amount,
                status,
                created_at,
                payment_id
            FROM payments
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )

        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()