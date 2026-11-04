
from datetime import datetime, timedelta, timezone

from db import get_db_connection


def create_gallery_record_and_consume_credit(
    user_id,
    storage_key,
    original_filename,
    output_filename,
    file_size_bytes,
    retention_days=30,
):
    """
    Insert the gallery record and consume one encryption credit
    in the same database transaction.

    Return False if the user has no remaining credits.
    Raise an exception if a database operation fails.
    """

    if retention_days <= 0:
        raise ValueError("Retention period must be greater than zero.")

    expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(days=retention_days)
    )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Consume one credit inside this transaction.
        cursor.execute(
            """
            UPDATE encryption_limits
            SET remaining_attempts = remaining_attempts - 1
            WHERE user_id = %s
              AND remaining_attempts > 0
            """,
            (user_id,),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return False

        # Register the encrypted image.
        cursor.execute(
            """
            INSERT INTO gallery (
                user_id,
                image_path,
                original_filename,
                output_filename,
                file_size_bytes,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                storage_key,
                original_filename,
                output_filename,
                file_size_bytes,
                expires_at,
            ),
        )

        connection.commit()
        return True

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

def get_user_gallery(user_id):
    """Return unexpired gallery records belonging to this user."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                image_path,
                original_filename,
                output_filename,
                file_size_bytes,
                uploaded_at,
                expires_at
            FROM gallery
            WHERE user_id = %s
              AND expires_at > UTC_TIMESTAMP()
            ORDER BY uploaded_at DESC
            """,
            (user_id,),
        )

        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def get_user_gallery_image(user_id, image_id):
    """Return one unexpired image belonging to this user."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, image_path, output_filename, expires_at
            FROM gallery
            WHERE id = %s
              AND user_id = %s
              AND expires_at > UTC_TIMESTAMP()
            """,
            (image_id, user_id),
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def delete_user_gallery_record(user_id, image_id):
    """Delete only a gallery record owned by this user."""

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM gallery
            WHERE id = %s
              AND user_id = %s
            """,
            (image_id, user_id),
        )

        deleted = cursor.rowcount == 1
        connection.commit()

        return deleted

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

def get_user_gallery(user_id):
    """Return unexpired encrypted images belonging to one user."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                image_path,
                original_filename,
                output_filename,
                file_size_bytes,
                uploaded_at,
                expires_at
            FROM gallery
            WHERE user_id = %s
              AND expires_at > UTC_TIMESTAMP()
            ORDER BY uploaded_at DESC
            """,
            (user_id,)
        )

        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_user_gallery_image(user_id, image_id):
    """Return one unexpired image belonging to the specified user."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                image_path,
                original_filename,
                output_filename,
                file_size_bytes,
                uploaded_at,
                expires_at
            FROM gallery
            WHERE id = %s
              AND user_id = %s
              AND expires_at > UTC_TIMESTAMP()
            LIMIT 1
            """,
            (image_id, user_id)
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def delete_user_gallery_record(user_id, image_id):
    """Delete a gallery record belonging to the specified user."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM gallery
            WHERE id = %s
              AND user_id = %s
            """,
            (image_id, user_id)
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

def get_user_gallery_image_for_delete(user_id, image_id):
    """Return an image record for its owner, including expired records."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, image_path
            FROM gallery
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (image_id, user_id)
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()