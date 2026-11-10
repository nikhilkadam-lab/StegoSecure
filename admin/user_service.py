
from db import get_db_connection


def get_users(limit=15, before_id=None, search="", status="all"):
    """
    Fetch one batch of users using ID-based cursor pagination.

    Search is applied on the complete database before pagination.
    """

    connection = None
    cursor = None

    try:
        limit = max(1, min(int(limit), 25))

        if before_id is not None:
            before_id = int(before_id)
            if before_id < 1:
                raise ValueError("Invalid pagination cursor.")

        search = (search or "").strip()[:100]

        if status not in ("all", "active", "disabled"):
            raise ValueError("Invalid account status filter.")

        conditions = []
        params = []

        if before_id is not None:
            conditions.append("u.id < %s")
            params.append(before_id)

        if search:
            conditions.append(
                "(u.username LIKE %s OR u.email LIKE %s)"
            )
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        if status == "active":
            conditions.append("u.is_active = 1")
        elif status == "disabled":
            conditions.append("u.is_active = 0")

        where_clause = (
            "WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = f"""
            SELECT
                u.id,
                u.username,
                u.email,
                u.created_at,
                u.is_active,

                COALESCE(el.remaining_attempts, 0)
                    AS remaining_credits,

                COALESCE(p.total_purchased_credits, 0)
                    AS total_purchased_credits

            FROM users u

            LEFT JOIN encryption_limits el
                ON el.user_id = u.id

            LEFT JOIN (
                SELECT
                    user_id,
                    SUM(COALESCE(credits_snapshot, 0))
                        AS total_purchased_credits

                FROM payments

                WHERE status = 'success'

                GROUP BY user_id
            ) p ON p.user_id = u.id

            {where_clause}

            ORDER BY u.id DESC

            LIMIT %s
        """

        params.append(limit + 1)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]

        for user in rows:
            if user["created_at"]:
                user["created_at"] = user["created_at"].isoformat()

            user["is_active"] = bool(user["is_active"])

        next_cursor = rows[-1]["id"] if rows and has_more else None

        return {
            "users": rows,
            "has_more": has_more,
            "next_cursor": next_cursor,
        }

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()



def update_user_status(user_id, is_active):
    connection = None
    cursor = None

    try:
        user_id = int(user_id)

        if user_id < 1 or not isinstance(is_active, bool):
            raise ValueError("Invalid account details.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM users WHERE id = %s FOR UPDATE",
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:
            raise ValueError("User not found.")

        cursor.execute(
            "UPDATE users SET is_active = %s WHERE id = %s",
            (int(is_active), user_id)
        )

        connection.commit()

        return is_active

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def update_user_credits(user_id, remaining_credits):
    connection = None
    cursor = None

    try:
        user_id = int(user_id)
        remaining_credits = int(remaining_credits)

        if user_id < 1:
            raise ValueError("Invalid user.")

        if remaining_credits < 0:
            raise ValueError("Credits cannot be negative.")

        if remaining_credits > 100000000:
            raise ValueError("Credit balance is too large.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM users WHERE id = %s FOR UPDATE",
            (user_id,)
        )

        if not cursor.fetchone():
            raise ValueError("User not found.")

        cursor.execute(
            """
            SELECT user_id
            FROM encryption_limits
            WHERE user_id = %s
            FOR UPDATE
            """,
            (user_id,)
        )

        credit_record = cursor.fetchone()

        if not credit_record:
            raise ValueError(
                "Credit record not found for this user."
            )

        cursor.execute(
            """
            UPDATE encryption_limits
            SET remaining_attempts = %s
            WHERE user_id = %s
            """,
            (remaining_credits, user_id)
        )

        connection.commit()

        return remaining_credits

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
