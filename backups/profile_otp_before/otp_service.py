import os
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from db import get_db_connection
from services.email_service import send_email


otp_hasher = PasswordHasher()


def _settings():
    length = int(os.getenv("OTP_LENGTH", "6"))
    expiry_minutes = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
    cooldown_seconds = int(os.getenv("OTP_RESEND_COOLDOWN", "60"))
    max_attempts = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    max_sends = int(os.getenv("OTP_MAX_SENDS", "3"))
    window_minutes = int(os.getenv("OTP_SEND_WINDOW_MINUTES", "15"))

    if length != 6:
        raise RuntimeError("OTP_LENGTH must be 6.")
    if min(expiry_minutes, cooldown_seconds, max_attempts,
           max_sends, window_minutes) <= 0:
        raise RuntimeError("OTP settings must be positive.")

    return (
        expiry_minutes,
        cooldown_seconds,
        max_attempts,
        max_sends,
        window_minutes,
    )


def _otp_email_content(code, purpose, expiry_minutes):
    purpose_text = {
        "registration": "complete your StegoSecure registration",
        "user_password_reset": "reset your StegoSecure password",
        "admin_login": "complete your StegoSecure administrator login",
    }.get(purpose, "verify your StegoSecure account")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;
                color:#172033;line-height:1.6">
      <h2 style="color:#087f9c">StegoSecure verification</h2>
      <p>Use this one-time password to {purpose_text}:</p>
      <div style="font-size:32px;font-weight:700;letter-spacing:8px;
                  padding:16px;background:#f1f7fa;text-align:center">
        {code}
      </div>
      <p>This code expires in {expiry_minutes} minutes.</p>
      <p>If you did not request this, you can ignore this email.</p>
      <p style="color:#687386;font-size:12px">
        StegoSecure will never ask you to share this code.
      </p>
    </div>
    """
    plain = (
        f"Your StegoSecure verification code is {code}. "
        f"It expires in {expiry_minutes} minutes. "
        "Do not share this code with anyone."
    )
    return html, plain


def issue_otp(email, purpose, pending_username=None,
              pending_password_hash=None):
    """
    Create and email a purpose-bound OTP.
    Only the Argon2 hash is stored in RDS.
    """
    (
        expiry_minutes,
        cooldown_seconds,
        max_attempts,
        max_sends,
        window_minutes,
    ) = _settings()

    now = datetime.utcnow()
    otp = f"{secrets.randbelow(1_000_000):06d}"
    otp_hash = otp_hasher.hash(otp)

    connection = None
    cursor = None
    challenge_id = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        connection.start_transaction()

        # Serialize issuance for this email/purpose when a prior row exists.
        cursor.execute(
            """
            SELECT id, last_sent_at
            FROM otp_challenges
            WHERE email = %s AND purpose = %s
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (email, purpose),
        )
        latest = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS send_total
            FROM otp_challenges
            WHERE email = %s
              AND purpose = %s
              AND created_at >= %s
            """,
            (
                email,
                purpose,
                now - timedelta(minutes=window_minutes),
            ),
        )
        send_total = cursor.fetchone()["send_total"]

        if latest:
            last_sent_at = latest["last_sent_at"]
            elapsed = (now - last_sent_at).total_seconds()
            if elapsed < cooldown_seconds:
                wait_seconds = max(1, int(cooldown_seconds - elapsed))
                raise ValueError(
                    f"Please wait {wait_seconds} seconds before requesting another code."
                )

        if send_total >= max_sends:
            raise ValueError(
                "You have reached the OTP send limit. Please try again later."
            )

        # Invalidate any earlier unused challenge for this purpose.
        cursor.execute(
            """
            UPDATE otp_challenges
            SET consumed_at = %s
            WHERE email = %s
              AND purpose = %s
              AND consumed_at IS NULL
            """,
            (now, email, purpose),
        )

        cursor.execute(
            """
            INSERT INTO otp_challenges (
                email, purpose, otp_hash, pending_username,
                pending_password_hash, expires_at, attempts,
                send_count, last_sent_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 0, 1, %s)
            """,
            (
                email,
                purpose,
                otp_hash,
                pending_username,
                pending_password_hash,
                now + timedelta(minutes=expiry_minutes),
                now,
            ),
        )
        challenge_id = cursor.lastrowid
        connection.commit()

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    html, plain = _otp_email_content(otp, purpose, expiry_minutes)

    try:
        send_email(
            to_email=email,
            subject="Your StegoSecure verification code",
            html_content=html,
            text_content=plain,
        )
    except Exception:
        # A code that could not be delivered must not remain usable.
        invalidate_otp(challenge_id)
        raise

    return {
        "challenge_id": challenge_id,
        "expires_in_minutes": expiry_minutes,
    }


def verify_otp(email, purpose, submitted_otp):
    """
    Verify a code and mark the challenge verified.
    The caller must consume it after completing the protected operation.
    """
    (
        _expiry_minutes,
        _cooldown_seconds,
        max_attempts,
        _max_sends,
        _window_minutes,
    ) = _settings()

    if (
        not isinstance(submitted_otp, str)
        or len(submitted_otp) != 6
        or not submitted_otp.isdigit()
    ):
        raise ValueError("Enter the 6-digit verification code.")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        connection.start_transaction()

        cursor.execute(
            """
            SELECT id, otp_hash, expires_at, attempts,
                   pending_username, pending_password_hash, verified_at
            FROM otp_challenges
            WHERE email = %s
              AND purpose = %s
              AND consumed_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (email, purpose),
        )
        challenge = cursor.fetchone()

        if not challenge:
            raise ValueError("The verification code is invalid or expired.")

        now = datetime.utcnow()

        if challenge["expires_at"] <= now:
            cursor.execute(
                "UPDATE otp_challenges SET consumed_at = %s WHERE id = %s",
                (now, challenge["id"]),
            )
            connection.commit()
            raise ValueError("The verification code has expired. Request a new one.")

        if challenge["attempts"] >= max_attempts:
            cursor.execute(
                "UPDATE otp_challenges SET consumed_at = %s WHERE id = %s",
                (now, challenge["id"]),
            )
            connection.commit()
            raise ValueError("Too many incorrect attempts. Request a new code.")

        try:
            matches = otp_hasher.verify(
                challenge["otp_hash"],
                submitted_otp,
            )
        except (
            VerifyMismatchError,
            VerificationError,
            InvalidHashError,
        ):
            matches = False

        if not matches:
            new_attempts = challenge["attempts"] + 1
            cursor.execute(
                """
                UPDATE otp_challenges
                SET attempts = %s,
                    consumed_at = CASE WHEN %s >= %s THEN %s
                                       ELSE consumed_at END
                WHERE id = %s
                """,
                (
                    new_attempts,
                    new_attempts,
                    max_attempts,
                    now,
                    challenge["id"],
                ),
            )
            connection.commit()
            if new_attempts >= max_attempts:
                raise ValueError("Too many incorrect attempts. Request a new code.")
            raise ValueError("The verification code is incorrect.")

        if not challenge["verified_at"]:
            cursor.execute(
                """
                UPDATE otp_challenges
                SET verified_at = %s
                WHERE id = %s AND consumed_at IS NULL
                """,
                (now, challenge["id"]),
            )

        connection.commit()
        return {
            "challenge_id": challenge["id"],
            "pending_username": challenge["pending_username"],
            "pending_password_hash": challenge["pending_password_hash"],
        }

    except Exception:
        if connection and connection.in_transaction:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def consume_verified_otp(challenge_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE otp_challenges
            SET consumed_at = UTC_TIMESTAMP()
            WHERE id = %s
              AND verified_at IS NOT NULL
              AND consumed_at IS NULL
              AND expires_at > UTC_TIMESTAMP()
            """,
            (challenge_id,),
        )
        connection.commit()
        return cursor.rowcount == 1

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def invalidate_otp(challenge_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE otp_challenges
            SET consumed_at = UTC_TIMESTAMP()
            WHERE id = %s AND consumed_at IS NULL
            """,
            (challenge_id,),
        )
        connection.commit()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
