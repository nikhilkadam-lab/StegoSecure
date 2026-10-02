import re


EMAIL_MAX_LENGTH = 255
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_email(email):
    if not isinstance(email, str):
        return None

    email = email.strip().lower()

    if not email or len(email) > EMAIL_MAX_LENGTH:
        return None

    if not EMAIL_PATTERN.fullmatch(email):
        return None

    return email


def validate_password(password):
    if not isinstance(password, str):
        return False, "Password is required."

    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        return (
            False,
            f"Password must be between {PASSWORD_MIN_LENGTH} "
            f"and {PASSWORD_MAX_LENGTH} characters.",
        )

    if password != password.strip():
        return False, "Password must not start or end with whitespace."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."

    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must contain at least one special character."

    return True, None
