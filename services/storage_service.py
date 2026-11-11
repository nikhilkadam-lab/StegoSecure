import os
import uuid
from pathlib import Path, PurePosixPath

import boto3
from botocore.exceptions import ClientError

from config import BASE_DIR


AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET = os.getenv("S3_BUCKET")

if not S3_BUCKET:
    raise RuntimeError("S3_BUCKET is missing from the .env file.")

s3_client = boto3.client("s3", region_name=AWS_REGION)


# Retain local storage support for any existing local images.
_storage_setting = os.getenv("ENCRYPTED_STORAGE_DIR", "private_storage")
_storage_path = Path(_storage_setting)

if not _storage_path.is_absolute():
    _storage_path = BASE_DIR / _storage_path

STORAGE_ROOT = _storage_path.resolve()


def _get_safe_path(storage_key):
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
    """Upload an encrypted PNG to private S3 storage."""

    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user ID.")

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Invalid encrypted image data.")

    filename = f"{uuid.uuid4().hex}.png"
    storage_key = f"encrypted-images/user_{user_id}/{filename}"

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=storage_key,
        Body=image_bytes,
        ContentType="image/png",
        ServerSideEncryption="AES256",
    )

    return storage_key, len(image_bytes)


def get_encrypted_image_path(storage_key):
    """
    Return local path for legacy images.
    Return image bytes for S3 images.
    """

    if not storage_key:
        raise ValueError("Storage key is required.")

    # New S3 storage keys.
    if storage_key.startswith("encrypted-images/"):
        try:
            response = s3_client.get_object(
                Bucket=S3_BUCKET,
                Key=storage_key,
            )
            return response["Body"].read()

        except s3_client.exceptions.NoSuchKey:
            return None

        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in (
                "NoSuchKey",
                "404",
            ):
                return None
            raise

    # Legacy local storage keys.
    path = _get_safe_path(storage_key)

    if not path.is_file():
        return None

    return path


def delete_encrypted_image(storage_key):
    """Delete an encrypted image from S3 or legacy local storage."""

    if not storage_key:
        raise ValueError("Storage key is required.")

    if storage_key.startswith("encrypted-images/"):
        s3_client.delete_object(
            Bucket=S3_BUCKET,
            Key=storage_key,
        )
        return True

    path = _get_safe_path(storage_key)

    if not path.is_file():
        return False

    path.unlink()
    return True