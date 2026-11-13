import mysql.connector
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from db import get_db_connection
from utils.validators import (
    normalize_email,
    validate_username,
    validate_password,
)

from services.otp_service import issue_otp, verify_otp

password_hasher = PasswordHasher()

def start_registration(username, email, password):
    username = validate_username(username)
    email = normalize_email(email)
    validate_password(password)

    password_hash = password_hasher.hash(password)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s OR username = %s
            LIMIT 1
            """,
            (email, username),
        )

        if cursor.fetchone():
            raise ValueError(
                "That email or username may already be registered."
            )

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    issue_otp(
        email=email,
        purpose="registration",
        pending_username=username,
        pending_password_hash=password_hash,
    )

    return email


def complete_registration(email, submitted_otp):
    email = normalize_email(email)

    challenge = verify_otp(
        email=email,
        purpose="registration",
        submitted_otp=submitted_otp,
    )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        connection.start_transaction()

        cursor.execute(
            """
            SELECT id, pending_username, pending_password_hash
            FROM otp_challenges
            WHERE id = %s
              AND email = %s
              AND purpose = 'registration'
              AND verified_at IS NOT NULL
              AND consumed_at IS NULL
              AND expires_at > UTC_TIMESTAMP()
            FOR UPDATE
            """,
            (challenge["challenge_id"], email),
        )

        verified_challenge = cursor.fetchone()

        if not verified_challenge:
            raise ValueError(
                "Your verification session has expired. Please request a new code."
            )

        username = verified_challenge["pending_username"]
        password_hash = verified_challenge["pending_password_hash"]

        if not username or not password_hash:
            raise ValueError(
                "Registration details are missing. Please start again."
            )

        cursor.execute(
            """
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = %s
            """,
            ("default_encryption_limit",),
        )

        setting = cursor.fetchone()
        encryption_limit = int(setting["setting_value"]) if setting else 5

        cursor.execute(
            """
            INSERT INTO users
                (username, email, password_hash, email_verified, is_active)
            VALUES (%s, %s, %s, TRUE, TRUE)
            """,
            (username, email, password_hash),
        )

        user_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO encryption_limits
                (user_id, remaining_attempts)
            VALUES (%s, %s)
            """,
            (user_id, encryption_limit),
        )

        cursor.execute(
            """
            UPDATE otp_challenges
            SET consumed_at = UTC_TIMESTAMP()
            WHERE id = %s
            """,
            (verified_challenge["id"],),
        )

        connection.commit()

        return {
            "id": user_id,
            "username": username,
            "email": email,
        }

    except mysql.connector.IntegrityError:
        if connection:
            connection.rollback()
        raise ValueError(
            "That email or username may already be registered."
        )

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def register_user(username, email, password):
    # Validate and normalize user input
    username = validate_username(username)
    email = normalize_email(email)
    validate_password(password)

    # Hash the password before storing it
    password_hash = password_hasher.hash(password)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Read the default encryption limit
        cursor.execute(
            """
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = %s
            """,
            ("default_encryption_limit",),
        )

        setting = cursor.fetchone()
        encryption_limit = int(setting["setting_value"]) if setting else 5

        # Create the user and their encryption limit atomically
        cursor.execute(
            """
            INSERT INTO users
                (username, email, password_hash, email_verified, is_active)
            VALUES (%s, %s, %s, FALSE, TRUE)
            """,
            (username, email, password_hash),
        )

        user_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO encryption_limits
                (user_id, remaining_attempts)
            VALUES (%s, %s)
            """,
            (user_id, encryption_limit),
        )

        connection.commit()

        return {
            "id": user_id,
            "username": username,
            "email": email,
        }

    except mysql.connector.IntegrityError:
        if connection:
            connection.rollback()
        raise ValueError(
            "That email or username may already be registered."
        )

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def authenticate_user(email, password):
    # Use the same generic error for invalid login attempts
    invalid_credentials = "Invalid email or password."

    try:
        email = normalize_email(email)
    except ValueError:
        raise ValueError(invalid_credentials)

    if not isinstance(password, str) or not password:
        raise ValueError(invalid_credentials)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, username, email, password_hash, is_active
            FROM users
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )

        user = cursor.fetchone()

        if not user or not user["is_active"]:
            raise ValueError(invalid_credentials)

        try:
            password_hasher.verify(user["password_hash"], password)
        except (
            VerifyMismatchError,
            VerificationError,
            InvalidHashError,
        ):
            raise ValueError(invalid_credentials)

        # Return only safe account details, never the password hash
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
        }

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_user_profile(user_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, username, email, created_at
            FROM users
            WHERE id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def update_username(user_id, new_username):
    new_username = validate_username(new_username)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE id = %s LIMIT 1",
            (user_id,),
        )

        if not cursor.fetchone():
            raise ValueError("User account not found.")

        cursor.execute(
            """
            UPDATE users
            SET username = %s
            WHERE id = %s
            """,
            (new_username, user_id),
        )

        connection.commit()

        return new_username

    except mysql.connector.IntegrityError:
        if connection:
            connection.rollback()
        raise ValueError("That username is already taken.")

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def verify_current_password(user_id, current_password):
    if not isinstance(current_password, str) or not current_password:
        return False

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT password_hash
            FROM users
            WHERE id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        user = cursor.fetchone()

        if not user:
            return False

        try:
            return password_hasher.verify(
                user["password_hash"],
                current_password,
            )
        except (
            VerifyMismatchError,
            VerificationError,
            InvalidHashError,
        ):
            return False

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def update_user_password(user_id, new_password):
    validate_password(new_password)

    password_hash = password_hasher.hash(new_password)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
            """,
            (password_hash, user_id),
        )

        if cursor.rowcount == 0:
            raise ValueError("User account not found.")

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


def start_password_reset(email):
    """
    Send a password-reset OTP only when an active, verified account exists.
    The caller always displays the same public response.
    """
    email = normalize_email(email)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
              AND is_active = TRUE
              AND email_verified = TRUE
            LIMIT 1
            """,
            (email,),
        )

        user = cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    if not user:
        return email

    # Do not expose account existence or OTP cooldown details publicly.
    try:
        issue_otp(email=email, purpose="user_password_reset")
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Password-reset OTP could not be issued."
        )

    return email


def complete_password_reset(email, challenge_id, new_password):
    """
    Change the password only if this email has a verified, unused,
    unexpired password-reset OTP challenge.
    """
    email = normalize_email(email)
    validate_password(new_password)

    password_hash = password_hasher.hash(new_password)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        connection.start_transaction()

        cursor.execute(
            """
            SELECT id
            FROM otp_challenges
            WHERE id = %s
              AND email = %s
              AND purpose = 'user_password_reset'
              AND verified_at IS NOT NULL
              AND consumed_at IS NULL
              AND expires_at > UTC_TIMESTAMP()
            FOR UPDATE
            """,
            (challenge_id, email),
        )

        challenge = cursor.fetchone()

        if not challenge:
            raise ValueError(
                "Your verification has expired. Please start again."
            )

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE email = %s
              AND is_active = TRUE
              AND email_verified = TRUE
            """,
            (password_hash, email),
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Your verification has expired. Please start again."
            )

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

        if cursor.rowcount != 1:
            raise ValueError(
                "Your verification has expired. Please start again."
            )

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