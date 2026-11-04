
from db import get_db_connection


def get_remaining_credits(user_id):
    """
    Return the user's current encryption credit balance.
    Return None if the user has no credit record.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT remaining_attempts
            FROM encryption_limits
            WHERE user_id = %s
            """,
            (user_id,),
        )

        result = cursor.fetchone()

        if not result:
            return None

        return result["remaining_attempts"]

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def consume_encryption_credit(user_id):
    """
    Atomically consume one encryption credit.
    Return False if no credits remain.
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE encryption_limits
            SET remaining_attempts = remaining_attempts - 1
            WHERE user_id = %s
              AND remaining_attempts > 0
            """,
            (user_id,),
        )

        success = cursor.rowcount == 1

        if success:
            connection.commit()
        else:
            connection.rollback()

        return success

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
