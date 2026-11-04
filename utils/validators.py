import re
from email_validator import EmailNotValidError, validate_email


def normalize_email(email):
    if not isinstance(email, str):
        raise ValueError("Please enter a valid email address.")

    try:
        result = validate_email(
            email.strip(),
            check_deliverability=False,
        )
        return result.normalized.lower()
    except EmailNotValidError:
        raise ValueError("Please enter a valid email address.")


def validate_username(username):
    if not isinstance(username, str):
        raise ValueError("Please enter your name.")

    username = " ".join(username.split())

    if not 2 <= len(username) <= 50:
        raise ValueError("Name must be between 2 and 50 characters.")

    if not all(char.isalpha() or char in " .'-" for char in username):
        raise ValueError("Name can contain letters, spaces, dots, hyphens, and apostrophes only.")

    if not any(char.isalpha() for char in username):
        raise ValueError("Please enter a valid name.")

    return username


def validate_password(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError("Password must be between 8 and 128 characters.")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")

    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number.")

    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character.")

    return password


import warnings

from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename


# Maximum decoded cover image size: 12 million pixels.
MAX_IMAGE_PIXELS = 40_000_000

# Only these cover image formats are supported.
ALLOWED_IMAGE_FORMATS = {
    "PNG",
    "JPEG",
    "BMP",
    "WEBP",
}


def validate_cover_image(file_storage, max_pixels=MAX_IMAGE_PIXELS):
    """
    Validate an uploaded cover image using its actual file contents.

    Returns:
        Dictionary containing the detected image format and dimensions.
    """

    if not file_storage or not file_storage.filename:
        raise ValueError("Please select a cover image.")

    stream = file_storage.stream

    try:
        stream.seek(0)

        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(stream) as image:
                image_format = image.format
                width, height = image.size

                if image_format not in ALLOWED_IMAGE_FORMATS:
                    raise ValueError(
                        "Unsupported cover image format. "
                        "Use PNG, JPEG, BMP or WebP."
                    )

                if width <= 0 or height <= 0:
                    raise ValueError("Invalid cover image dimensions.")

                if width * height > max_pixels:
                    raise ValueError(
                        "Cover image is too large. "
                        "Maximum allowed resolution is 40 million pixels."
                    )

                image.verify()

            # Reopen and fully decode the image to detect corrupt files.
            stream.seek(0)

            with Image.open(stream) as image:
                image.load()

                if image.size != (width, height):
                    raise ValueError("Invalid cover image.")

        return {
            "format": image_format,
            "width": width,
            "height": height,
            "pixels": width * height,
        }

    except ValueError:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError(
            "The selected cover image is invalid, corrupted or too large."
        ) from exc

    finally:
        stream.seek(0)


def validate_secret_file(file_storage, max_bytes):
    """
    Validate an uploaded secret file's presence, filename and size.

    Returns:
        Dictionary containing a safe filename and file size.
    """

    if not file_storage or not file_storage.filename:
        raise ValueError("Please select a secret file.")

    stream = file_storage.stream

    try:
        stream.seek(0, 2)
        file_size = stream.tell()
        stream.seek(0)

        if file_size <= 0:
            raise ValueError("The selected secret file is empty.")

        if file_size > max_bytes:
            raise ValueError(
                "The secret file exceeds the maximum allowed file size."
            )

        safe_filename = secure_filename(file_storage.filename)

        if not safe_filename:
            safe_filename = "secret_file"

        return {
            "filename": safe_filename,
            "size": file_size,
        }

    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise

        raise ValueError(
            "Unable to read the selected secret file."
        ) from exc

    finally:
        stream.seek(0)