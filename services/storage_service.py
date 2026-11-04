
import os
import uuid
from pathlib import Path, PurePosixPath

from config import BASE_DIR


# Private local storage directory.
# This directory must never be placed inside Flask's static folder.
_storage_setting = os.getenv("ENCRYPTED_STORAGE_DIR", "private_storage")
_storage_path = Path(_storage_setting)

if not _storage_path.is_absolute():
    _storage_path = BASE_DIR / _storage_path

STORAGE_ROOT = _storage_path.resolve()


def _get_safe_path(storage_key):
    """
    Convert a relative storage key into a safe local filesystem path.
    Reject absolute paths and directory traversal.
    """
    if not storage_key:
        raise ValueError("Storage key is required.")

    key_path = PurePosixPath(storage_key)

    if key_path.is_absolute() or ".." in key_path.parts:
        raise ValueError("Invalid storage key.")

    full_path = (STORAGE_ROOT / Path(*key_path.parts)).resolve()

    try:
        full_path.relative_to(STORAGE_ROOT)
    except ValueError:
        raise ValueError("Invalid storage key.")

    return full_path


def save_encrypted_image(user_id, image_bytes):
    """
    Save an encrypted PNG privately and return its storage key and size.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user ID.")

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Invalid encrypted image data.")

    filename = f"{uuid.uuid4().hex}.png"
    storage_key = f"encrypted_images/user_{user_id}/{filename}"

    destination = _get_safe_path(storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = destination.with_suffix(".tmp")

    try:
        with temporary_path.open("xb") as file:
            file.write(image_bytes)

        temporary_path.replace(destination)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return storage_key, len(image_bytes)


def get_encrypted_image_path(storage_key):
    """
    Return the local path for an existing encrypted image.
    """
    path = _get_safe_path(storage_key)

    if not path.is_file():
        return None

    return path


def delete_encrypted_image(storage_key):
    """
    Delete an encrypted image from private local storage.
    """
    path = _get_safe_path(storage_key)

    if not path.is_file():
        return False

    path.unlink()
    return True
