
from datetime import date

from db import get_db_connection


def get_revenue_summary():
    """Return revenue totals for successful payments only."""

    connection = None
    cursor = None

    try:
        today = date.today()
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(amount), 0) AS total_revenue,

                COALESCE(SUM(
                    CASE
                        WHEN DATE(created_at) = CURDATE()
                        THEN amount ELSE 0
                    END
                ), 0) AS today_revenue,

                COALESCE(SUM(
                    CASE
                        WHEN YEAR(created_at) = YEAR(CURDATE())
                         AND MONTH(created_at) = MONTH(CURDATE())
                        THEN amount ELSE 0
                    END
                ), 0) AS monthly_revenue,

                COALESCE(SUM(
                    CASE
                        WHEN created_at >= %s
                        THEN amount ELSE 0
                    END
                ), 0) AS quarterly_revenue

            FROM payments
            WHERE status = 'success'
            """,
            (date(today.year, quarter_start_month, 1),),
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def get_transactions(
    status,
    limit=15,
    before_id=None,
    search="",
):
    """Fetch transactions for one status with cursor pagination."""

    connection = None
    cursor = None

    try:
        if status not in ("success", "pending", "failed"):
            raise ValueError("Invalid transaction status.")

        limit = max(1, min(int(limit), 25))

        if before_id is not None:
            before_id = int(before_id)
            if before_id < 1:
                raise ValueError("Invalid pagination cursor.")

        search = (search or "").strip()[:100]

        conditions = ["p.status = %s"]
        params = [status]

        if before_id is not None:
            conditions.append("p.id < %s")
            params.append(before_id)

        if search:
            conditions.append(
                """
                (
                    p.payment_id LIKE %s
                    OR p.razorpay_order_id LIKE %s
                    OR u.username LIKE %s
                    OR u.email LIKE %s
                )
                """
            )

            pattern = f"%{search}%"
            params.extend([pattern] * 4)

        where_clause = " AND ".join(conditions)

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            f"""
            SELECT
                p.id,
                p.payment_id,
                p.razorpay_order_id,
                p.user_id,
                u.username,
                u.email,

                COALESCE(
                    p.plan_name_snapshot,
                    pl.name,
                    'Credit Plan'
                ) AS plan_name,

                p.credits_snapshot,
                p.amount,
                p.status,
                p.created_at

            FROM payments p

            INNER JOIN users u
                ON u.id = p.user_id

            LEFT JOIN plans pl
                ON pl.id = p.plan_id

            WHERE {where_clause}

            ORDER BY p.id DESC

            LIMIT %s
            """,
            tuple(params + [limit + 1]),
        )

        rows = cursor.fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]

        for transaction in rows:
            if transaction["created_at"]:
                transaction["created_at"] = (
                    transaction["created_at"].isoformat()
                )

            transaction["amount"] = float(
                transaction["amount"]
            )

        next_cursor = (
            rows[-1]["id"] if rows and has_more else None
        )

        return {
            "transactions": rows,
            "has_more": has_more,
            "next_cursor": next_cursor,
        }

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
