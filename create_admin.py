import getpass

import mysql.connector
from argon2 import PasswordHasher
from mysql.connector import IntegrityError

from db import get_db_connection
from utils.validators import normalize_email, validate_password


password_hasher = PasswordHasher()


def create_admin():
    print("\n========== StegoSecure Admin Creation ==========\n")

    username = input("Enter admin username: ").strip()

    if not 2 <= len(username) <= 100:
        print("Username must be between 2 and 100 characters.")
        return

    try:
        email = normalize_email(input("Enter admin email: "))
    except ValueError as error:
        print(error)
        return

    password = getpass.getpass("Enter admin password: ")
    confirm_password = getpass.getpass("Confirm admin password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    # Reuse exactly the same password validation as user registration.
    try:
        validate_password(password)
    except ValueError as error:
        print(f"\nPassword validation failed: {error}")
        return

    password_hash = password_hasher.hash(password)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO admins
                (username, email, password_hash, is_active)
            VALUES (%s, %s, %s, TRUE)
            """,
            (username, email, password_hash),
        )

        connection.commit()

        print("\nAdmin account created successfully!")
        print(f"Username: {username}")
        print(f"Email: {email}")

    except IntegrityError:
        if connection:
            connection.rollback()

        print(
            "\nAn admin with this username or email already exists."
        )

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        print(f"\nDatabase error: {error}")

    except Exception as error:
        if connection:
            connection.rollback()

        print(f"\nUnexpected error: {error}")

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    create_admin()