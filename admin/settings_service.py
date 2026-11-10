from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from db import get_db_connection


ALLOWED_BANNER_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}
MAX_BANNER_BYTES = 8 * 1024 * 1024
MAX_BANNER_PIXELS = 25_000_000


def _banner_directory(instance_path):
    directory = Path(instance_path) / "banners"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_default_encryption_limit():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = %s
            LIMIT 1
            """,
            ("default_encryption_limit",),
        )
        row = cursor.fetchone()
        return int(row["setting_value"]) if row else 5
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def update_default_encryption_limit(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Enter a valid whole-number encryption limit.")
    if value < 0 or value > 1_000_000:
        raise ValueError("The encryption limit must be between 0 and 1,000,000.")

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO system_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            """,
            ("default_encryption_limit", value),
        )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def list_uploaded_banners(instance_path):
    directory = _banner_directory(instance_path)
    active_filename = None
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT setting_value FROM site_settings WHERE setting_key = %s LIMIT 1",
            ("active_banner",),
        )
        row = cursor.fetchone()
        if row:
            active_filename = row["setting_value"]
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    banners = []
    for path in directory.iterdir():
        if (
            path.is_file()
            and path.name.startswith("admin_")
            and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ):
            stat = path.stat()
            banners.append({
                "filename": path.name,
                "size_bytes": stat.st_size,
                "updated_at": stat.st_mtime,
                "is_active": path.name == active_filename,
            })

    banners.sort(key=lambda item: item["updated_at"], reverse=True)
    return banners


def save_uploaded_banner(file_storage, instance_path):
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a banner image to upload.")

    stream = file_storage.stream
    stream.seek(0, 2)
    file_size = stream.tell()
    stream.seek(0)

    if file_size <= 0 or file_size > MAX_BANNER_BYTES:
        raise ValueError("Banner image must be smaller than 8 MB.")

    try:
        image = Image.open(stream)
        image_format = image.format
        width, height = image.size
        image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("Upload a valid PNG, JPG, or WEBP image.")

    if image_format not in ALLOWED_BANNER_FORMATS:
        raise ValueError("Only PNG, JPG, and WEBP banner images are allowed.")
    if width <= 0 or height <= 0 or width * height > MAX_BANNER_PIXELS:
        raise ValueError("Banner image dimensions are too large.")

    filename = f"admin_{uuid4().hex}{ALLOWED_BANNER_FORMATS[image_format]}"
    directory = _banner_directory(instance_path)
    destination = directory / filename
    stream.seek(0)
    file_storage.save(destination)
    return filename


def _validate_uploaded_filename(filename, instance_path):
    if (
        not isinstance(filename, str)
        or not filename.startswith("admin_")
        or Path(filename).name != filename
        or Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
    ):
        raise ValueError("Invalid uploaded banner.")

    directory = _banner_directory(instance_path).resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise ValueError("Banner not found.")
    return path


def activate_banner(filename, instance_path):
    _validate_uploaded_filename(filename, instance_path)
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO site_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            """,
            ("active_banner", filename),
        )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def deactivate_banner(filename, instance_path):
    _validate_uploaded_filename(filename, instance_path)
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM site_settings WHERE setting_key = %s AND setting_value = %s",
            ("active_banner", filename),
        )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def delete_uploaded_banner(filename, instance_path):
    path = _validate_uploaded_filename(filename, instance_path)
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM site_settings WHERE setting_key = %s AND setting_value = %s",
            ("active_banner", filename),
        )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    path.unlink(missing_ok=True)
