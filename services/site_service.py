from pathlib import Path

from db import get_db_connection


def get_active_banner():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT setting_value
            FROM site_settings
            WHERE setting_key = %s
            """,
            ("active_banner",),
        )

        setting = cursor.fetchone()

        if setting:
            filename = setting["setting_value"]

            # Only accept a filename, never a directory path.
            if (
                filename
                and Path(filename).name == filename
                and Path(filename).suffix.lower()
                in {".png", ".jpg", ".jpeg", ".webp"}
            ):
                return filename

    except Exception:
        # Database errors must not prevent the public homepage
        # from displaying its default banner.
        pass

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

    return None