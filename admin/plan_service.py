
from db import get_db_connection


def get_all_plans():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                name,
                price,
                encryptions,
                is_active,
                created_at
            FROM plans
            ORDER BY price ASC, id ASC
        """)

        plans = cursor.fetchall()

        for plan in plans:
            plan["price"] = float(plan["price"])
            plan["is_active"] = bool(plan["is_active"])

            if plan["created_at"]:
                plan["created_at"] = plan["created_at"].isoformat()

        return plans

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def create_plan(name, price, credits, is_popular=False):
    connection = None
    cursor = None

    try:
        name = (name or "").strip()
        price = float(price)
        credits = int(credits)

        if not name or len(name) > 50:
            raise ValueError("Plan name must contain 1–50 characters.")

        if price < 0 or price > 100000000:
            raise ValueError("Enter a valid plan price.")

        if credits < 1 or credits > 100000000:
            raise ValueError("Credits must be between 1 and 100000000.")

        if not isinstance(is_popular, bool):
            raise ValueError("Invalid Popular selection.")

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO plans (name, price, encryptions, is_active)
            VALUES (%s, %s, %s, 1)
        """, (name, price, credits))

        plan_id = cursor.lastrowid

        if is_popular:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value)
                VALUES ('popular_plan_id', %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            """, (plan_id,))

        connection.commit()

        return plan_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()



def get_popular_plan_id():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = 'popular_plan_id'
        """)

        result = cursor.fetchone()
        return result["setting_value"] if result else None

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def update_plan(plan_id, name, price, credits, is_popular=False):
    connection = None
    cursor = None

    try:
        plan_id = int(plan_id)
        name = (name or "").strip()
        price = float(price)
        credits = int(credits)

        if plan_id < 1:
            raise ValueError("Invalid plan.")

        if not name or len(name) > 50:
            raise ValueError("Plan name must contain 1–50 characters.")

        if price < 0 or price > 100000000:
            raise ValueError("Enter a valid plan price.")

        if credits < 1 or credits > 100000000:
            raise ValueError("Credits must be between 1 and 100000000.")

        if not isinstance(is_popular, bool):
            raise ValueError("Invalid Popular selection.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, is_active
            FROM plans
            WHERE id = %s
            FOR UPDATE
        """, (plan_id,))

        plan = cursor.fetchone()

        if not plan:
            raise ValueError("Plan not found.")

        if is_popular and not plan["is_active"]:
            raise ValueError("A disabled plan cannot be Popular.")

        cursor.execute("""
            UPDATE plans
            SET name = %s, price = %s, encryptions = %s
            WHERE id = %s
        """, (name, price, credits, plan_id))

        if is_popular:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value)
                VALUES ('popular_plan_id', %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            """, (plan_id,))
        else:
            cursor.execute("""
                DELETE FROM system_settings
                WHERE setting_key = 'popular_plan_id'
                  AND setting_value = %s
            """, (plan_id,))

        connection.commit()
        return plan_id

    except Exception:
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def update_plan_status(plan_id, is_active):
    connection = None
    cursor = None

    try:
        plan_id = int(plan_id)

        if plan_id < 1 or not isinstance(is_active, bool):
            raise ValueError("Invalid plan status details.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id
            FROM plans
            WHERE id = %s
            FOR UPDATE
        """, (plan_id,))

        if not cursor.fetchone():
            raise ValueError("Plan not found.")

        cursor.execute("""
            UPDATE plans
            SET is_active = %s
            WHERE id = %s
        """, (int(is_active), plan_id))

        if not is_active:
            cursor.execute("""
                DELETE FROM system_settings
                WHERE setting_key = 'popular_plan_id'
                  AND setting_value = %s
            """, (plan_id,))

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


def delete_plan(plan_id):
    connection = None
    cursor = None

    try:
        plan_id = int(plan_id)

        if plan_id < 1:
            raise ValueError("Invalid plan.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id
            FROM plans
            WHERE id = %s
            FOR UPDATE
        """, (plan_id,))

        if not cursor.fetchone():
            raise ValueError("Plan not found.")

        cursor.execute("""
            SELECT COUNT(*) AS payment_count
            FROM payments
            WHERE plan_id = %s
        """, (plan_id,))

        result = cursor.fetchone()

        if result["payment_count"] > 0:
            raise ValueError(
                "This plan has payment records and cannot be deleted. "
                "Disable it instead."
            )

        cursor.execute("""
            DELETE FROM plans
            WHERE id = %s
        """, (plan_id,))

        cursor.execute("""
            DELETE FROM system_settings
            WHERE setting_key = 'popular_plan_id'
              AND setting_value = %s
        """, (plan_id,))

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
