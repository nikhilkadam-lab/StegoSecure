from functools import wraps

from flask import flash, redirect, session, url_for
from db import get_db_connection


def get_active_admin(admin_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, username, email
            FROM admins
            WHERE id = %s AND is_active = 1
            LIMIT 1
            """,
            (admin_id,),
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        admin_id = session.get("admin_id")

        if not admin_id:
            return redirect(url_for("admin.login"))

        try:
            admin = get_active_admin(admin_id)

        except Exception:
            session.pop("admin_id", None)
            session.pop("admin_username", None)
            session.pop("admin_email", None)

            flash("Please log in again.", "error")
            return redirect(url_for("admin.login"))

        if not admin:
            session.pop("admin_id", None)
            session.pop("admin_username", None)
            session.pop("admin_email", None)

            flash("Your admin access is inactive.", "error")
            return redirect(url_for("admin.login"))

        return view(*args, **kwargs)

    return wrapped_view