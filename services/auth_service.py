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

password_hasher = PasswordHasher()


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
