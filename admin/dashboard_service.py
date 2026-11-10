
from db import get_db_connection


def get_dashboard_statistics():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Revenue and overall statistics
        cursor.execute("""
            SELECT
                COALESCE(SUM(
                    CASE WHEN status = 'success'
                    THEN amount ELSE 0 END
                ), 0) AS all_time_revenue,

                COALESCE(SUM(
                    CASE WHEN status = 'success'
                    AND DATE(created_at) = CURDATE()
                    THEN amount ELSE 0 END
                ), 0) AS today_revenue,

                COALESCE(SUM(
                    CASE WHEN status = 'success'
                    AND YEAR(created_at) = YEAR(CURDATE())
                    AND MONTH(created_at) = MONTH(CURDATE())
                    THEN amount ELSE 0 END
                ), 0) AS monthly_revenue,

                COUNT(
                    CASE WHEN status = 'success' THEN 1 END
                ) AS successful_payments,

                COALESCE(SUM(
                    CASE WHEN status = 'success'
                    THEN COALESCE(credits_snapshot, 0)
                    ELSE 0 END
                ), 0) AS total_credits_sold

            FROM payments
        """)

        statistics = cursor.fetchone()

        # Total registered users
        cursor.execute("""
            SELECT COUNT(*) AS total_users
            FROM users
        """)

        statistics["total_users"] = cursor.fetchone()["total_users"]

        # Most purchased credit plan
        cursor.execute("""
            SELECT
                COALESCE(p.plan_name_snapshot, pl.name)
                    AS plan_name,
                COUNT(*) AS purchase_count

            FROM payments p
            LEFT JOIN plans pl ON pl.id = p.plan_id

            WHERE p.status = 'success'

            GROUP BY COALESCE(p.plan_name_snapshot, pl.name)

            ORDER BY purchase_count DESC, plan_name ASC
            LIMIT 1
        """)

        statistics["most_purchased_plan"] = cursor.fetchone()

        # Five most recent transactions
        cursor.execute("""
            SELECT
                p.id,
                p.payment_id,
                p.razorpay_order_id,
                u.username,
                u.email,
                COALESCE(
                    p.plan_name_snapshot,
                    pl.name,
                    'Credit Plan'
                ) AS plan_name,
                p.amount,
                p.credits_snapshot,
                p.status,
                p.created_at

            FROM payments p

            INNER JOIN users u ON u.id = p.user_id
            LEFT JOIN plans pl ON pl.id = p.plan_id

            ORDER BY p.created_at DESC, p.id DESC
            LIMIT 5
        """)

        recent_transactions = cursor.fetchall()

        # Five most recent registrations
        cursor.execute("""
            SELECT
                id,
                username,
                email,
                created_at

            FROM users

            ORDER BY created_at DESC, id DESC
            LIMIT 5
        """)

        recent_users = cursor.fetchall()

        return {
            "statistics": statistics,
            "recent_transactions": recent_transactions,
            "recent_users": recent_users,
        }

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
